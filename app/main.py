import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import Dict

from app.core.config import get_settings
from app.core.database import engine, Base, get_db
from app.models import (
    Puesto, Empleado, Usuario, Turno, Asistencia, Nomina,
    Proveedor, Ingrediente, Insumo, MovimientoInventario,
    CategoriaMenu, MenuItem, Receta,
    Zona, Mesa, EstadoMesa,
    Orden, DetalleOrden, EstadoOrden,
    CierreCaja,
    Gasto, CategoriaGasto,
)
from app.api.endpoints.personal import router as personal_router
from app.api.endpoints.asistencia import router as asistencia_router
from app.api.endpoints.nomina import router as nomina_router
from app.api.endpoints.inventario import router as inventario_router
from app.api.endpoints.menu import router as menu_router
from app.api.endpoints.salon import router as salon_router
from app.api.endpoints.orden import router as orden_router
from app.api.endpoints.analitica import router as analitica_router
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.reportes import router as reportes_router
from app.api.endpoints.caja import router as caja_router
from app.api.endpoints.gasto import router as gasto_router


settings = get_settings()

app = FastAPI(
    title="Sazón Caribeño API",
    description="Sistema Integral de Gestión para Restaurantes",
    version="1.0.0",
    debug=settings.DEBUG
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers de la API
app.include_router(
    personal_router,
    prefix="/api/v1/personal",
    tags=["Personal & Usuarios"]
)

app.include_router(
    asistencia_router,
    prefix="/api/v1/asistencia",
    tags=["Asistencias & Horarios"]
)

app.include_router(
    nomina_router,
    prefix="/api/v1/nomina",
    tags=["Nóminas & Pagos"]
)

app.include_router(
    inventario_router,
    prefix="/api/v1/inventario",
    tags=["Inventario & Proveedores"]
)

app.include_router(
    menu_router,
    prefix="/api/v1/menu",
    tags=["Menú y Recetas"]
)

app.include_router(
    salon_router,
    prefix="/api/v1/salon",
    tags=["Salón y Mesas"]
)

app.include_router(
    orden_router,
    prefix="/api/v1/ordenes",
    tags=["Órdenes y Facturación"]
)

app.include_router(
    analitica_router,
    prefix="/api/v1/analitica",
    tags=["Analítica y Finanzas"]
)

app.include_router(
    reportes_router,
    prefix="/api/v1/reportes",
    tags=["Reportes y Cierres"]
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Autenticación"]
)

app.include_router(
    caja_router,
    prefix="/api/v1/caja",
    tags=["Caja y Cierres"]
)

app.include_router(
    gasto_router,
    prefix="/api/v1/gastos",
    tags=["Gastos"]
)

app.mount("/Templates", StaticFiles(directory="app/Templates"), name="Templates")


@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación."""
    Base.metadata.create_all(bind=engine)
    _migrate_constraints()
    _migrate_unidades_medida()
    _migrate_recetas_unidad()
    _migrate_insumos_empaque()
    _migrate_orden_mesa_nullable()
    _migrate_recetas_descuento_lote()
    _fix_unidades_medida()
    _auto_seed_admin()
    _fix_joshi_password()
    _fix_orphaned_mesas()
    asyncio.create_task(_heartbeat_watcher())


def _migrate_constraints():
    """Aplica migraciones de constraints que create_all no actualiza."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            db.execute(text(
                "ALTER TABLE puestos DROP CHECK ck_puestos_salario_positivo"
            ))
        except Exception:
            pass
        try:
            db.execute(text(
                "ALTER TABLE puestos ADD CONSTRAINT ck_puestos_salario_positivo "
                "CHECK (salario_base >= 0)"
            ))
            db.commit()
        except Exception:
            db.rollback()


def _migrate_unidades_medida():
    """Agrega columnas de conversión a unidades_medida si no existen."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    cols = [
        ("tipo_magnitud", "ALTER TABLE unidades_medida ADD COLUMN tipo_magnitud VARCHAR(20) NOT NULL DEFAULT 'UNIDAD'"),
        ("unidad_base_id", "ALTER TABLE unidades_medida ADD COLUMN unidad_base_id INT NULL"),
        ("factor_conversion", "ALTER TABLE unidades_medida ADD COLUMN factor_conversion FLOAT NULL"),
    ]
    with Session(engine) as db:
        for col_name, ddl in cols:
            try:
                db.execute(text(ddl))
                db.commit()
                print(f"  [~] Columna '{col_name}' agregada a unidades_medida")
            except Exception:
                db.rollback()


def _migrate_recetas_unidad():
    """Agrega columna unidad_medida_id a recetas si no existe."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            db.execute(text(
                "ALTER TABLE recetas ADD COLUMN unidad_medida_id INT NULL"
            ))
            db.commit()
            print("  [~] Columna 'unidad_medida_id' agregada a recetas")
        except Exception:
            db.rollback()


def _migrate_insumos_empaque():
    """Agrega columnas de empaque a insumos si no existen."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        for col, typedef in [
            ("unidad_empaque_id", "INT NULL"),
            ("factor_empaque", "DOUBLE NULL"),
        ]:
            try:
                db.execute(text(f"ALTER TABLE insumos ADD COLUMN {col} {typedef}"))
                db.commit()
                print(f"  [~] Columna '{col}' agregada a insumos")
            except Exception:
                db.rollback()


def _migrate_orden_mesa_nullable():
    """Hace nullable la columna mesa_id en ordenes para ventas directas."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            db.execute(text(
                "ALTER TABLE ordenes MODIFY COLUMN mesa_id INT NULL"
            ))
            db.commit()
        except Exception:
            db.rollback()


def _migrate_recetas_descuento_lote():
    """Agrega columna descuento_por_lote a recetas si no existe."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            db.execute(text(
                "ALTER TABLE recetas ADD COLUMN descuento_por_lote BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            db.commit()
            print("  [~] Columna 'descuento_por_lote' agregada a recetas")
        except Exception:
            db.rollback()


def _fix_unidades_medida():
    """Corrige magnitudes y cadenas de conversión de unidades existentes.

    - Actualiza tipo_magnitud para unidades conocidas que pudieran tener el valor incorrecto.
    - Establece unidad_base_id y factor_conversion donde falten.
    - Agrega unidades estándar que no existan (Onza, Libra, Botella, Lata, Par, Bolsa, Porción).
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import Session
    from app.models.inventario import UnidadMedida

    CORRECCIONES = {
        "Kilogramo":  {"tipo_magnitud": "PESO"},
        "Gramo":      {"tipo_magnitud": "PESO"},
        "Libra":      {"tipo_magnitud": "PESO"},
        "Onza":       {"tipo_magnitud": "PESO"},
        "Litro":      {"tipo_magnitud": "VOLUMEN"},
        "Mililitro":  {"tipo_magnitud": "VOLUMEN"},
        "Botella":    {"tipo_magnitud": "VOLUMEN"},
        "Lata":       {"tipo_magnitud": "VOLUMEN"},
        "Unidad":     {"tipo_magnitud": "UNIDAD"},
        "Docena":     {"tipo_magnitud": "UNIDAD"},
        "Par":        {"tipo_magnitud": "UNIDAD"},
        "Paquete":    {"tipo_magnitud": "UNIDAD"},
        "Bolsa":      {"tipo_magnitud": "UNIDAD"},
        "Porción":    {"tipo_magnitud": "UNIDAD"},
    }

    CONVERSIONES = {
        "Kilogramo": {"base": "Gramo",  "factor": 1000.0},
        "Libra":     {"base": "Gramo",  "factor": 453.592},
        "Onza":      {"base": "Gramo",  "factor": 28.3495},
        "Litro":     {"base": "Mililitro", "factor": 1000.0},
        "Botella":   {"base": "Mililitro", "factor": 1000.0},
        "Lata":      {"base": "Mililitro", "factor": 355.0},
        "Docena":    {"base": "Unidad", "factor": 12.0},
        "Par":       {"base": "Unidad", "factor": 2.0},
    }

    NUEVAS = {
        "Onza":    {"abreviatura": "oz",  "tipo_magnitud": "PESO"},
        "Libra":   {"abreviatura": "lb",  "tipo_magnitud": "PESO"},
        "Botella": {"abreviatura": "Bot", "tipo_magnitud": "VOLUMEN"},
        "Lata":    {"abreviatura": "Lta", "tipo_magnitud": "VOLUMEN"},
        "Par":     {"abreviatura": "Pr",  "tipo_magnitud": "UNIDAD"},
        "Bolsa":   {"abreviatura": "Bol", "tipo_magnitud": "UNIDAD"},
        "Porción": {"abreviatura": "Por", "tipo_magnitud": "UNIDAD"},
    }

    with Session(engine) as db:
        all_units = db.execute(select(UnidadMedida)).scalars().all()
        existing = {u.nombre: u for u in all_units}
        existing_abrev = {u.abreviatura.lower(): u for u in all_units}

        for nombre, data in NUEVAS.items():
            if nombre not in existing and data["abreviatura"].lower() not in existing_abrev:
                unit = UnidadMedida(nombre=nombre, abreviatura=data["abreviatura"], tipo_magnitud=data["tipo_magnitud"])
                db.add(unit)
                db.flush()
                existing[nombre] = unit
                existing_abrev[data["abreviatura"].lower()] = unit
                print(f"  [+] Unidad creada: {nombre} ({data['abreviatura']}) [{data['tipo_magnitud']}]")

        for nombre, corr in CORRECCIONES.items():
            if nombre in existing:
                unit = existing[nombre]
                new_mag = corr.get("tipo_magnitud")
                if new_mag and unit.tipo_magnitud != new_mag:
                    old = unit.tipo_magnitud
                    unit.tipo_magnitud = new_mag
                    print(f"  [~] {nombre}: magnitud {old} → {new_mag}")

        for nombre, conv in CONVERSIONES.items():
            if nombre in existing:
                unit = existing[nombre]
                base_name = conv["base"]
                if base_name in existing:
                    base_id = existing[base_name].id
                    needs_update = (
                        unit.unidad_base_id != base_id
                        or unit.factor_conversion != conv["factor"]
                    )
                    if needs_update:
                        unit.unidad_base_id = base_id
                        unit.factor_conversion = conv["factor"]
                        print(f"  [~] {nombre} → base: {base_name} (factor: {conv['factor']})")

        db.commit()


def _auto_seed_admin():
    """Crea un usuario administrador si la tabla usuarios está vacía."""
    from datetime import date
    from decimal import Decimal
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.core.security import obtener_password_hash
    from app.models.personal import Puesto, Empleado, Usuario

    with Session(engine) as db:
        try:
            existe = db.execute(select(Usuario).limit(1)).scalar_one_or_none()
            if existe:
                return

            print("  ▸ Tabla 'usuarios' vacía — creando administrador automático...")

            stmt = select(Puesto).where(Puesto.nombre == "Administrador")
            puesto = db.execute(stmt).scalar_one_or_none()
            if not puesto:
                puesto = Puesto(nombre="Administrador", salario_base=Decimal("1200.00"))
                db.add(puesto)
                db.flush()

            empleado = Empleado(
                cedula_identidad="ADMIN-001",
                nombre="Administrador",
                apellido="Sistema",
                puesto_id=puesto.id,
                salario_base=puesto.salario_base,
                fecha_ingreso=date.today(),
                activo=True,
            )
            db.add(empleado)
            db.flush()

            usuario = Usuario(
                username="joshi_0211",
                password_hash=obtener_password_hash("@0420311001000V"),
                rol="Administrador",
                empleado_id=empleado.id,
                activo=True,
            )
            db.add(usuario)
            db.commit()

            print("    [+] Administrador creado: joshi_0211")
        except Exception as e:
            db.rollback()
            print(f"  [!] Error al crear administrador automático: {e}")


def _fix_joshi_password():
    """TEMP: Re-hashea la contraseña de joshi_0211 con bcrypt directo (fix passlib migration)."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.core.security import obtener_password_hash

    with Session(engine) as db:
        try:
            row = db.execute(
                text("SELECT id FROM usuarios WHERE username = 'joshi_0211' LIMIT 1")
            ).fetchone()
            if not row:
                return
            new_hash = obtener_password_hash("@0420311001000V")
            db.execute(
                text("UPDATE usuarios SET password_hash = :h WHERE username = 'joshi_0211'"),
                {"h": new_hash},
            )
            db.commit()
            print("  [AUTH FIX] Contraseña de joshi_0211 actualizada")
        except Exception as e:
            db.rollback()
            print(f"  [!] Error en auth fix: {e}")


def _fix_orphaned_mesas():
    """Libera mesas OCUPADA que no tienen orden activa asociada."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            result = db.execute(text("""
                UPDATE mesas
                SET estado = 'LIBRE'
                WHERE estado = 'OCUPADA'
                  AND id NOT IN (
                    SELECT DISTINCT ordenes.mesa_id
                    FROM ordenes
                    WHERE ordenes.mesa_id IS NOT NULL
                      AND ordenes.estado IN ('PENDIENTE', 'PREPARANDO', 'ENTREGADA')
                  )
            """))
            if result.rowcount > 0:
                db.commit()
                print(f"  [SALON] {result.rowcount} mesa(s) huérfana(s) liberada(s) automáticamente")
            else:
                db.rollback()
        except Exception as e:
            db.rollback()
            print(f"  [!] Error al liberar mesas huérfanas: {e}")


async def _heartbeat_watcher():
    """Tarea en segundo plano: cierra automáticamente turnos sin heartbeat."""
    from app.services.asistencia_service import AsistenciaService
    while True:
        await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SECONDS)
        try:
            db = next(get_db())
            try:
                svc = AsistenciaService(db)
                svc.cerrar_turnos_stale(settings.HEARTBEAT_TIMEOUT_SECONDS)
            except Exception:
                pass
            finally:
                db.close()
        except Exception:
            pass


@app.get(
    "/healthcheck",
    tags=["Sistema"],
    summary="Verificar estado del sistema"
)
def healthcheck() -> Dict[str, str]:
    """
    Endpoint de verificación de salud del sistema.

    Retorna el estado del servidor y la marca de tiempo.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Sazón Caribeño API",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
