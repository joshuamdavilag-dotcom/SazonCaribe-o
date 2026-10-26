import json
import os
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import Date, DateTime, Time, desc, select, text

from app.core.database import Base
from app.models import (
    Puesto, Empleado, Usuario, Turno, Asistencia, Nomina, AdelantoSalario,
    UnidadMedida, CategoriaInsumo, Insumo, MovimientoInventario,
    CategoriaMenu, MenuItem, Receta,
    Zona, Mesa, Orden, DetalleOrden,
    CierreCaja, CategoriaGasto, Gasto,
    EventoCalendario, RegistroAuditoria, BackupSistema
)
from app.services.auditoria_service import AuditoriaService

BACKUP_DIR = Path("app/backups")
BACKUP_TABLE = "backups_sistema"
MAX_BACKUPS = 24  # se conservan las últimas 24 copias (2 años de copias mensuales)
DIAS_ENTRE_COPIAS = 30


def _serialize_value(val: Any) -> Any:
    """Convierte un valor de BD a algo serializable en JSON."""
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, Enum):
        return val.value
    return val



def _json_serializer(obj: Any) -> Any:
    """Serializa objetos no nativos JSON (datetime, date, Decimal, Enum)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Tipo {type(obj)} no es serializable en JSON")


class BackupService:
    """Servicio de gestión de copias de seguridad (Backups) del sistema."""

    def __init__(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _model_to_dict(self, instance: Any) -> Dict[str, Any]:
        """Convierte una instancia SQLAlchemy a diccionario serializable."""
        data = {}
        for column in instance.__table__.columns:
            val = getattr(instance, column.name)
            if isinstance(val, (datetime, date)):
                data[column.name] = val.isoformat()
            elif isinstance(val, Decimal):
                data[column.name] = float(val)
            elif isinstance(val, Enum):
                data[column.name] = val.value
            else:
                data[column.name] = val
        return data

    def crear_backup(self, db: Session, actor: Optional[Usuario] = None) -> Dict[str, Any]:
        """Genera un archivo JSON de respaldo con todos los datos del sistema."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sazon_backup_{now_str}.json"
        filepath = BACKUP_DIR / filename

        tables_data: Dict[str, List[Dict[str, Any]]] = {}
        total_records = 0

        model_map = [
            ("puestos", Puesto),
            ("empleados", Empleado),
            ("usuarios", Usuario),
            ("turnos", Turno),
            ("asistencias", Asistencia),
            ("nominas", Nomina),
            ("adelantos_salario", AdelantoSalario),
            ("unidades_medida", UnidadMedida),
            ("categorias_insumo", CategoriaInsumo),
            ("insumos", Insumo),
            ("categorias_menu", CategoriaMenu),
            ("menu_items", MenuItem),
            ("recetas", Receta),
            ("zonas", Zona),
            ("mesas", Mesa),
            ("ordenes", Orden),
            ("detalles_orden", DetalleOrden),
            ("cierres_caja", CierreCaja),
            ("categorias_gasto", CategoriaGasto),
            ("gastos", Gasto),
            ("eventos_calendario", EventoCalendario),
            ("auditoria", RegistroAuditoria),
        ]

        for table_key, model_cls in model_map:
            records = db.execute(select(model_cls)).scalars().all()
            serialized = [self._model_to_dict(r) for r in records]
            tables_data[table_key] = serialized
            total_records += len(serialized)

        backup_payload = {
            "metadata": {
                "sistema": "Sazón Caribeño POS",
                "version": "1.0",
                "fecha_creacion": datetime.now().isoformat(),
                "registrado_por_usuario_id": actor.id if actor else None,
                "total_registros": total_records,
                "tablas": list(tables_data.keys())
            },
            "datos": tables_data
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, indent=2, ensure_ascii=False, default=_json_serializer)

        file_size_bytes = filepath.stat().st_size
        file_size_kb = round(file_size_bytes / 1024, 2)

        if actor:
            AuditoriaService.registrar(
                db=db,
                actor=actor,
                accion="CREAR_BACKUP",
                entidad_tipo="BACKUP",
                entidad_id=None,
                descripcion=f"Copia de seguridad '{filename}' creada ({file_size_kb} KB, {total_records} registros)"
            )
            db.commit()

        return {
            "filename": filename,
            "filepath": str(filepath),
            "size_kb": file_size_kb,
            "total_records": total_records,
            "fecha_creacion": backup_payload["metadata"]["fecha_creacion"]
        }

    def listar_backups(self) -> List[Dict[str, Any]]:
        """Lista todas las copias de seguridad guardadas en el servidor."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backups = []
        for file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                stat = file.stat()
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = data.get("metadata", {})
                backups.append({
                    "filename": file.name,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "fecha_creacion": meta.get("fecha_creacion", datetime.fromtimestamp(stat.st_mtime).isoformat()),
                    "total_registros": meta.get("total_registros", 0),
                    "sistema": meta.get("sistema", "Sazón Caribeño POS")
                })
            except Exception:
                backups.append({
                    "filename": file.name,
                    "size_kb": round(file.stat().st_size / 1024, 2),
                    "fecha_creacion": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "total_registros": 0,
                    "sistema": "Desconocido"
                })
        return backups

    def obtener_ruta_backup(self, filename: str) -> Optional[Path]:
        """Obtiene la ruta validada del archivo de copia previniendo Path Traversal."""
        safe_name = os.path.basename(filename)
        filepath = (BACKUP_DIR / safe_name).resolve()
        if not str(filepath).startswith(str(BACKUP_DIR.resolve())):
            return None
        if not filepath.exists() or not filepath.is_file():
            return None
        return filepath

    def eliminar_backup(self, filename: str, db: Session, actor: Optional[Usuario] = None) -> bool:
        """Elimina una copia de seguridad del servidor."""
        filepath = self.obtener_ruta_backup(filename)
        if not filepath:
            return False
        filepath.unlink()

        if actor and db:
            AuditoriaService.registrar(
                db=db,
                actor=actor,
                accion="ELIMINAR_BACKUP",
                entidad_tipo="BACKUP",
                entidad_id=None,
                descripcion=f"Copia de seguridad '{filename}' eliminada del servidor"
            )
            db.commit()
        return True

    # =========================================================================
    # Copias de seguridad almacenadas en la base de datos
    # =========================================================================

    def generar_payload(self, db: Session) -> Dict[str, Any]:
        """Serializa todas las tablas del sistema (excepto la de copias)."""
        tablas: Dict[str, List[Dict[str, Any]]] = {}
        total = 0
        for table in Base.metadata.sorted_tables:
            if table.name == BACKUP_TABLE:
                continue
            filas = [
                {col: _serialize_value(row[col]) for col in row.keys()}
                for row in db.execute(select(table)).mappings()
            ]
            tablas[table.name] = filas
            total += len(filas)

        return {
            "metadata": {
                "sistema": "Sazón Caribeño POS",
                "version": "2.0",
                "fecha_creacion": datetime.now().isoformat(),
                "total_registros": total,
                "tablas": list(tablas.keys()),
            },
            "datos": tablas,
        }

    def crear_backup_bd(
        self,
        db: Session,
        actor: Optional[Usuario] = None,
        origen: str = "manual",
    ) -> Dict[str, Any]:
        """Genera una copia y la guarda dentro de la base de datos."""
        payload = self.generar_payload(db)
        contenido = json.dumps(
            payload, ensure_ascii=False, default=_json_serializer
        )
        nombre = f"sazon_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        registro = BackupSistema(
            nombre=nombre,
            origen=origen,
            creado_en=datetime.now(),
            total_registros=payload["metadata"]["total_registros"],
            tamano_bytes=len(contenido.encode("utf-8")),
            contenido=contenido,
            creado_por=actor.id if actor else None,
        )
        db.add(registro)
        db.commit()
        db.refresh(registro)

        self._purgar_backups(db)

        if actor:
            AuditoriaService.registrar(
                db=db,
                actor=actor,
                accion="CREAR_BACKUP",
                entidad_tipo="BACKUP",
                entidad_id=registro.id,
                descripcion=(
                    f"Copia de seguridad '{nombre}' creada ({origen}, "
                    f"{registro.total_registros} registros, "
                    f"{round(registro.tamano_bytes / 1024, 2)} KB)"
                ),
            )
            db.commit()

        return self._backup_a_dict(registro)

    def crear_si_corresponde_mensual(self, db: Session) -> Optional[Dict[str, Any]]:
        """Crea la copia automática si pasaron 30 días desde la última."""
        ultima = db.execute(
            select(BackupSistema)
            .where(BackupSistema.origen == "automatico")
            .order_by(desc(BackupSistema.creado_en))
        ).scalars().first()

        if ultima and (datetime.now() - ultima.creado_en) < timedelta(days=DIAS_ENTRE_COPIAS):
            return None

        return self.crear_backup_bd(db, actor=None, origen="automatico")

    def listar_backups_bd(self, db: Session) -> List[Dict[str, Any]]:
        """Lista las copias guardadas en la BD (sin incluir el contenido)."""
        registros = db.execute(
            select(BackupSistema).order_by(desc(BackupSistema.creado_en))
        ).scalars().all()
        return [self._backup_a_dict(r) for r in registros]

    def obtener_backup_bd(self, db: Session, backup_id: int) -> Optional[BackupSistema]:
        """Obtiene una copia concreta por ID."""
        return db.get(BackupSistema, backup_id)

    def estado(self, db: Session) -> Dict[str, Any]:
        """Resumen para la interfaz: última copia y próxima automática."""
        backups = self.listar_backups_bd(db)
        automaticas = [b for b in backups if b["origen"] == "automatico"]
        ultima = backups[0] if backups else None
        proxima = None
        if automaticas:
            fecha = datetime.fromisoformat(automaticas[0]["creado_en"])
            proxima = (fecha + timedelta(days=DIAS_ENTRE_COPIAS)).isoformat()

        return {
            "total": len(backups),
            "ultima": ultima,
            "ultima_automatica": automaticas[0] if automaticas else None,
            "proxima_automatica": proxima,
            "frecuencia_dias": DIAS_ENTRE_COPIAS,
        }

    def eliminar_backup_bd(
        self,
        db: Session,
        backup_id: int,
        actor: Optional[Usuario] = None,
    ) -> bool:
        """Elimina una copia guardada en la BD."""
        registro = db.get(BackupSistema, backup_id)
        if not registro:
            return False
        nombre = registro.nombre
        db.delete(registro)
        db.commit()

        if actor:
            AuditoriaService.registrar(
                db=db,
                actor=actor,
                accion="ELIMINAR_BACKUP",
                entidad_tipo="BACKUP",
                entidad_id=backup_id,
                descripcion=f"Copia de seguridad '{nombre}' eliminada",
            )
            db.commit()
        return True

    def restaurar_backup_bd(
        self,
        db: Session,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Restaura un backup reemplazando los datos de las tablas incluidas.

        Solo toca las tablas presentes en el archivo: si un backup viejo no
        trae alguna tabla, esa tabla se deja intacta.
        """
        datos = payload.get("datos")
        if not isinstance(datos, dict) or not datos:
            raise ValueError("El archivo no contiene datos para restaurar")

        tablas_por_nombre = {
            t.name: t for t in Base.metadata.sorted_tables if t.name != BACKUP_TABLE
        }
        desconocidas = [nombre for nombre in datos if nombre not in tablas_por_nombre]
        if desconocidas:
            raise ValueError(
                "El archivo contiene tablas desconocidas: " + ", ".join(desconocidas[:5])
            )

        # Borrar de hijos a padres e insertar de padres a hijos (orden de FKs).
        try:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name in datos:
                    db.execute(table.delete())

            insertados = 0
            for table in Base.metadata.sorted_tables:
                if table.name not in datos:
                    continue
                filas = sorted(
                    datos.get(table.name) or [],
                    key=lambda fila: fila.get("id") or 0,
                )
                limpias = [self._coerce_row(table, fila) for fila in filas]
                if limpias:
                    db.execute(table.insert(), limpias)
                insertados += len(limpias)

            self._reset_secuencias(db)
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.expire_all()
        return {
            "tablas": len(datos),
            "registros": insertados,
            "fecha_backup": (payload.get("metadata") or {}).get("fecha_creacion"),
        }

    def _coerce_row(self, table: Any, fila: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte fechas/horas ISO a objetos Python (SQLite no acepta str)."""
        resultado: Dict[str, Any] = {}
        for col in table.columns:
            if col.name not in fila:
                continue
            valor = fila[col.name]
            if isinstance(valor, str):
                try:
                    if isinstance(col.type, DateTime):
                        valor = datetime.fromisoformat(valor)
                    elif isinstance(col.type, Date):
                        valor = date.fromisoformat(valor[:10])
                    elif isinstance(col.type, Time):
                        valor = time.fromisoformat(valor)
                except ValueError:
                    pass
            resultado[col.name] = valor
        return resultado

    def _reset_secuencias(self, db: Session) -> None:
        """Reajusta los SERIAL de PostgreSQL tras insertar IDs explícitos."""
        if db.get_bind().dialect.name != "postgresql":
            return
        for table in Base.metadata.sorted_tables:
            if "id" not in table.columns:
                continue
            try:
                db.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{table.name}\"), 0) + 1, false)"
                ))
            except Exception:
                continue

    def _purgar_backups(self, db: Session) -> None:
        """Conserva solo las últimas MAX_BACKUPS copias."""
        ids = db.execute(
            select(BackupSistema.id)
            .order_by(desc(BackupSistema.creado_en))
            .offset(MAX_BACKUPS)
        ).scalars().all()
        for backup_id in ids:
            registro = db.get(BackupSistema, backup_id)
            if registro:
                db.delete(registro)
        if ids:
            db.commit()

    def _backup_a_dict(self, registro: BackupSistema) -> Dict[str, Any]:
        return {
            "id": registro.id,
            "nombre": registro.nombre,
            "origen": registro.origen,
            "creado_en": registro.creado_en.isoformat(),
            "total_registros": registro.total_registros,
            "tamano_kb": round(registro.tamano_bytes / 1024, 2),
            "creado_por": registro.creado_por,
        }


backup_service = BackupService()
