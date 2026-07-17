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
    _auto_seed_admin()
    asyncio.create_task(_heartbeat_watcher())


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
                username="Joshi_0211",
                password_hash=obtener_password_hash("@0420311001000V"),
                rol="Administrador",
                empleado_id=empleado.id,
                activo=True,
            )
            db.add(usuario)
            db.commit()

            print("    [+] Administrador creado: Joshi_0211")
        except Exception as e:
            db.rollback()
            print(f"  [!] Error al crear administrador automático: {e}")


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
