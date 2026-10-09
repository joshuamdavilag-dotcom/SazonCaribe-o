import json
import os
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.core.database import Base
from app.models import (
    Puesto, Empleado, Usuario, Turno, Asistencia, Nomina, AdelantoSalario,
    UnidadMedida, CategoriaInsumo, Insumo, MovimientoInventario,
    CategoriaMenu, MenuItem, Receta,
    Zona, Mesa, Orden, DetalleOrden,
    CierreCaja, CategoriaGasto, Gasto,
    EventoCalendario, RegistroAuditoria
)
from app.services.auditoria_service import AuditoriaService

BACKUP_DIR = Path("app/backups")


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


backup_service = BackupService()
