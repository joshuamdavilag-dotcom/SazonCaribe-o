import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import Dict

from app.core.config import get_settings
from app.core.database import engine, Base, get_db
from app.models import (
    Puesto, Empleado, Usuario, Turno, Asistencia, Nomina, AdelantoSalario,
    Proveedor, Ingrediente, Insumo, MovimientoInventario,
    CategoriaMenu, MenuItem, Receta,
    Zona, Mesa, EstadoMesa,
    Orden, DetalleOrden, EstadoOrden,
    CierreCaja,
    Gasto, CategoriaGasto,
    PagoOnline, EstadoPago,
    EventoCalendario,
    Camera, CameraAccess, CameraClip,
    RegistroAuditoria,
)
from app.api.endpoints.personal import router as personal_router
from app.api.endpoints.asistencia import router as asistencia_router
from app.api.endpoints.nomina import router as nomina_router
from app.api.endpoints.inventario import router as inventario_router
from app.api.endpoints.menu import router as menu_router
from app.api.endpoints.menu_publico import router as menu_publico_router
from app.api.endpoints.salon import router as salon_router
from app.api.endpoints.orden import router as orden_router
from app.api.endpoints.analitica import router as analitica_router
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.reportes import router as reportes_router
from app.api.endpoints.caja import router as caja_router
from app.api.endpoints.gasto import router as gasto_router
from app.api.endpoints.descuento import router as descuento_router
from app.api.endpoints.pagos import router as pagos_router
from app.api.endpoints.calendario import router as calendario_router
from app.api.endpoints.cameras import router as cameras_router
from app.api.auditoria import router as auditoria_router
from app.api.endpoints.backups import router as backups_router
from app.api.endpoints.push import router as push_router
from app.api.endpoints.estudio_mercado import router as estudio_mercado_router


settings = get_settings()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sazón Caribeño API",
    description="Sistema Integral de Gestión para Restaurantes",
    version="1.0.0",
    debug=False,
)


@app.exception_handler(Exception)
async def manejador_error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """Registra el detalle internamente y devuelve un error genérico al cliente."""
    logger.error(
        "Error no controlado en %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocurrió un error inesperado. Intenta nuevamente."},
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

app.include_router(
    descuento_router,
    prefix="/api/v1/descuentos",
    tags=["Descuentos"]
)

app.include_router(
    pagos_router,
    prefix="/api/v1/pagos",
    tags=["Pagos en línea"]
)

app.include_router(
    calendario_router,
    prefix="/api/v1/calendario",
    tags=["Calendario"]
)

app.include_router(
    cameras_router,
    prefix="/api/v1/cameras",
    tags=["Cámaras de seguridad"]
)

app.include_router(
    auditoria_router,
    prefix="/api/v1/auditoria",
    tags=["Auditoría"]
)

app.include_router(
    backups_router,
    prefix="/api/v1/backups",
    tags=["Copias de Seguridad"]
)

app.include_router(
    push_router,
    prefix="/api/v1/push",
    tags=["Notificaciones Push"]
)

app.include_router(
    estudio_mercado_router,
    prefix="/api/v1/estudio-mercado",
    tags=["Estudio de Mercado"]
)

app.include_router(
    menu_publico_router,
    prefix="/api/public",
    tags=["Carta Pública (Menú Digital)"]
)

app.mount("/Templates", StaticFiles(directory="app/Templates"), name="Templates")

# Carta Digital pública (menú para clientes). Se sirve en /carta/ y consume
# la API pública /api/public (sin autenticación).
app.mount(
    "/carta",
    StaticFiles(directory="app/Templates/carta", html=True),
    name="carta",
)


@app.middleware("http")
async def _revalidar_estaticos(request: Request, call_next):
    """Los assets del ERP y de la Carta se revalidan siempre (ETag/304).

    Así las URLs de los archivos son estables (nunca hay que versionarlas)
    y el navegador nunca queda con una copia vieja del JS o del CSS.
    """
    response = await call_next(request)
    ruta = request.url.path
    if ruta.startswith("/Templates") or ruta.startswith("/carta"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación."""
    try:
        Base.metadata.create_all(bind=engine)
        _migrate_calendario_color()
        _migrate_calendario_columnas()
        _migrate_constraints()
        _migrate_unidades_medida()
        _migrate_recetas_unidad()
        _migrate_insumos_empaque()
        _migrate_orden_mesa_nullable()
        _migrate_recetas_descuento_lote()
        _migrate_orden_descuentos()
        _migrate_orden_nombre_cliente()
        _migrate_orden_metodo_pago()
        _migrate_descuentos_frecuentes()
        _migrate_gastos_cierre_caja_id()
        _migrate_adelantos_salario()
        _migrate_menu_item_imagen_tiempo()
        _migrate_asistencia_utc_a_local()
        _migrate_asistencias_anulada()
        _migrate_usuarios_turno_habilitado()
        _migrate_usuarios_avisos_fuera_de_turno()
        _migrate_usuarios_avisos_comandas()
        _migrate_mesas_apodo()
        _migrate_ordenes_anulacion()
        _migrate_gastos_eliminacion()
        _migrate_nombres_archivados()
        _fix_unidades_medida()
        _auto_seed_admin()
        _fix_joshi_password()
        _seed_harca27_admin()
        _auditar_hashes()
        _fix_orphaned_mesas()
        _sancar_turnos_huerfanos()
    except Exception as e:
        logger.error("Error durante las migraciones o inicio de BD: %s", e, exc_info=True)

    asyncio.create_task(_heartbeat_watcher())
    asyncio.create_task(_camera_clip_retention_watcher())
    asyncio.create_task(_estudio_mercado_watcher())


def _is_sqlite() -> bool:
    """Detecta si estamos usando SQLite."""
    return settings.DATABASE_URL.startswith("sqlite")


def _column_exists(table: str, column: str) -> bool:
    """Verifica si una columna existe (compatible MySQL/SQLite)."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return False
    cols = {col["name"] for col in inspector.get_columns(table)}
    return column in cols


def _table_exists(table: str) -> bool:
    """Verifica si una tabla existe."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    return inspector.has_table(table)


def _migrate_calendario_color():
    """Agrega la etiqueta de color a eventos existentes sin alterar sus datos."""
    from sqlalchemy import text
    if not _table_exists("eventos_calendario"):
        # create_all ya debería haberla creado, pero por si acaso
        return
    if _column_exists("eventos_calendario", "color_etiqueta"):
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE eventos_calendario ADD COLUMN color_etiqueta VARCHAR(20) NULL"))
    logger.info("Migración de color_etiqueta aplicada a eventos_calendario")


def _migrate_constraints():
    """Aplica migraciones de constraints que create_all no actualiza."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        if not _is_sqlite():
            # PostgreSQL: el constraint se define en el modelo; create_all ya lo aplica.
            # Solo elimina la versión previa si existe con otro nombre/forma.
            try:
                db.execute(text(
                    "ALTER TABLE puestos DROP CONSTRAINT IF EXISTS ck_puestos_salario_positivo"
                ))
                db.commit()
            except Exception:
                db.rollback()
            try:
                db.execute(text(
                    "ALTER TABLE puestos ADD CONSTRAINT ck_puestos_salario_positivo "
                    "CHECK (salario_base >= 0)"
                ))
                db.commit()
            except Exception:
                db.rollback()
            return
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


def _add_column_if_not_exists(table: str, column: str, ddl: str):
    """Agrega columna si no existe (compatible SQLite/MySQL)."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    if _column_exists(table, column):
        print(f"  [~] Columna '{column}' ya existe en {table}")
        return
    with Session(engine) as db:
        try:
            db.execute(text(ddl))
            db.commit()
            print(f"  [~] Columna '{column}' agregada a {table}")
        except Exception as e:
            db.rollback()
            print(f"  [X] Error agregando '{column}' a {table}: {e}")


def _migrate_unidades_medida():
    """Agrega columnas de conversión a unidades_medida si no existen."""
    _add_column_if_not_exists("unidades_medida", "tipo_magnitud",
        "ALTER TABLE unidades_medida ADD COLUMN tipo_magnitud VARCHAR(20) NOT NULL DEFAULT 'UNIDAD'")
    _add_column_if_not_exists("unidades_medida", "unidad_base_id",
        "ALTER TABLE unidades_medida ADD COLUMN unidad_base_id INT NULL")
    _add_column_if_not_exists("unidades_medida", "factor_conversion",
        "ALTER TABLE unidades_medida ADD COLUMN factor_conversion FLOAT NULL")


def _migrate_recetas_unidad():
    """Agrega columna unidad_medida_id a recetas si no existe."""
    _add_column_if_not_exists("recetas", "unidad_medida_id",
        "ALTER TABLE recetas ADD COLUMN unidad_medida_id INT NULL")


def _migrate_insumos_empaque():
    """Agrega columnas de empaque a insumos si no existen."""
    _add_column_if_not_exists("insumos", "unidad_empaque_id",
        "ALTER TABLE insumos ADD COLUMN unidad_empaque_id INT NULL")
    _add_column_if_not_exists("insumos", "factor_empaque",
        "ALTER TABLE insumos ADD COLUMN factor_empaque FLOAT NULL")


def _migrate_orden_mesa_nullable():
    """En SQLite no se puede MODIFY COLUMN, create_all ya lo crea nullable si el modelo lo define.
    Esta migración es solo para MySQL legacy. En SQLite no hace nada."""
    pass  # SQLite no requiere esta migración


def _migrate_recetas_descuento_lote():
    """Agrega columna descuento_por_lote a recetas si no existe."""
    _add_column_if_not_exists("recetas", "descuento_por_lote",
        "ALTER TABLE recetas ADD COLUMN descuento_por_lote BOOLEAN NOT NULL DEFAULT FALSE")


def _migrate_orden_descuentos():
    """Agrega columnas de descuento a ordenes y detalles_orden si no existen."""
    _add_column_if_not_exists("ordenes", "subtotal",
        "ALTER TABLE ordenes ADD COLUMN subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00")
    _add_column_if_not_exists("ordenes", "descuento_total",
        "ALTER TABLE ordenes ADD COLUMN descuento_total DECIMAL(10,2) NOT NULL DEFAULT 0.00")
    _add_column_if_not_exists("detalles_orden", "descuento_porcentaje",
        "ALTER TABLE detalles_orden ADD COLUMN descuento_porcentaje DECIMAL(5,2) NULL")
    _add_column_if_not_exists("detalles_orden", "descuento_monto",
        "ALTER TABLE detalles_orden ADD COLUMN descuento_monto DECIMAL(10,2) NULL")
    _add_column_if_not_exists("detalles_orden", "motivo_descuento",
        "ALTER TABLE detalles_orden ADD COLUMN motivo_descuento VARCHAR(255) NULL")

    # Migración de datos (compatible SQLite/MySQL)
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        try:
            db.execute(text("UPDATE ordenes SET subtotal = total WHERE subtotal = 0 AND total > 0"))
            db.execute(text("UPDATE ordenes SET descuento_total = 0 WHERE descuento_total IS NULL"))
            db.commit()
        except Exception:
            db.rollback()


def _migrate_orden_nombre_cliente():
    """Agrega columna nombre_cliente a ordenes si no existe."""
    _add_column_if_not_exists("ordenes", "nombre_cliente",
        "ALTER TABLE ordenes ADD COLUMN nombre_cliente VARCHAR(100) NULL")


def _migrate_orden_metodo_pago():
    """Agrega la forma de pago a las órdenes y normaliza las existentes."""
    from sqlalchemy import text

    _add_column_if_not_exists(
        "ordenes",
        "metodo_pago",
        "ALTER TABLE ordenes ADD COLUMN metodo_pago VARCHAR(20) NOT NULL DEFAULT 'EFECTIVO'",
    )
    try:
        with engine.begin() as conexion:
            conexion.execute(
                text(
                    "UPDATE ordenes SET metodo_pago = 'EFECTIVO' "
                    "WHERE metodo_pago IS NULL OR metodo_pago = ''"
                )
            )
    except Exception as error:
        logger.warning("[MIGRACION] No se pudo normalizar metodo_pago: %s", error)


def _migrate_descuentos_frecuentes():
    """Crea la tabla descuentos_frecuentes y siembra descuentos comunes la primera vez."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    if not _table_exists("descuentos_frecuentes"):
        return  # create_all ya la crea con el modelo

    with Session(engine) as db:
        try:
            existentes = db.execute(
                text("SELECT COUNT(*) FROM descuentos_frecuentes")
            ).scalar_one()
            if existentes and int(existentes) > 0:
                return
            semillas = [
                ("Empleado 20%", "PORCENTAJE", 20.00),
                ("Promo 10%", "PORCENTAJE", 10.00),
                ("Cliente frecuente 5%", "PORCENTAJE", 5.00),
                ("Cortesía C$50", "MONTO", 50.00),
            ]
            for nombre, tipo, valor in semillas:
                db.execute(
                    text(
                        "INSERT INTO descuentos_frecuentes (nombre, tipo, valor, activo) "
                        "VALUES (:n, :t, :v, :a)"
                    ),
                    {"n": nombre, "t": tipo, "v": valor, "a": True},
                )
            db.commit()
            logger.info("Descuentos frecuentes sembrados: %s", len(semillas))
        except Exception as e:
            db.rollback()
            logger.warning("No se pudieron sembrar descuentos frecuentes: %s", e)


def _migrate_gastos_cierre_caja_id():
    """Agrega la columna cierre_caja_id a gastos y su FK si no existen."""
    _add_column_if_not_exists("gastos", "cierre_caja_id",
        "ALTER TABLE gastos ADD COLUMN cierre_caja_id INT NULL")

    # FK en SQLite se crea en create_all si el modelo lo define
    # En MySQL legacy, esta migración la agregaba; en SQLite no hace falta
    pass


def _migrate_ordenes_anulacion():
    """Agrega las columnas de anulación a ordenes y devolución a detalles_orden."""
    _add_column_if_not_exists("ordenes", "anulada",
        "ALTER TABLE ordenes ADD COLUMN anulada BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_not_exists("ordenes", "motivo_anulacion",
        "ALTER TABLE ordenes ADD COLUMN motivo_anulacion VARCHAR(255) NULL")
    _add_column_if_not_exists("ordenes", "anulada_por",
        "ALTER TABLE ordenes ADD COLUMN anulada_por INT NULL")
    _add_column_if_not_exists("ordenes", "anulada_en",
        "ALTER TABLE ordenes ADD COLUMN anulada_en DATETIME NULL")
    _add_column_if_not_exists("detalles_orden", "cantidad_devuelta",
        "ALTER TABLE detalles_orden ADD COLUMN cantidad_devuelta INT NOT NULL DEFAULT 0")
    _add_column_if_not_exists("detalles_orden", "motivo_devolucion",
        "ALTER TABLE detalles_orden ADD COLUMN motivo_devolucion VARCHAR(255) NULL")
    _add_column_if_not_exists("detalles_orden", "devuelta_en",
        "ALTER TABLE detalles_orden ADD COLUMN devuelta_en DATETIME NULL")


def _migrate_gastos_eliminacion():
    """Agrega las columnas de borrado lógico a gastos."""
    _add_column_if_not_exists("gastos", "eliminado",
        "ALTER TABLE gastos ADD COLUMN eliminado BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_not_exists("gastos", "motivo_eliminacion",
        "ALTER TABLE gastos ADD COLUMN motivo_eliminacion VARCHAR(255) NULL")
    _add_column_if_not_exists("gastos", "eliminado_por",
        "ALTER TABLE gastos ADD COLUMN eliminado_por INT NULL")
    _add_column_if_not_exists("gastos", "eliminado_en",
        "ALTER TABLE gastos ADD COLUMN eliminado_en DATETIME NULL")


def _migrate_adelantos_salario():
    """Crea la tabla adelantos_salario y agrega columna total_adelantos a nominas si no existen."""
    # create_all ya crea la tabla si el modelo está definido
    _add_column_if_not_exists("nominas", "total_adelantos",
        "ALTER TABLE nominas ADD COLUMN total_adelantos DECIMAL(10,2) NOT NULL DEFAULT 0.00")


def _migrate_menu_item_imagen_tiempo():
    """Agrega columnas imagen_url y tiempo_preparacion a menu_items si no existen."""
    _add_column_if_not_exists("menu_items", "imagen_url",
        "ALTER TABLE menu_items ADD COLUMN imagen_url VARCHAR(500) NULL")
    _add_column_if_not_exists("menu_items", "tiempo_preparacion",
        "ALTER TABLE menu_items ADD COLUMN tiempo_preparacion INT NULL")


def _migrate_asistencia_utc_a_local():
    """Migración one-time: convierte timestamps de asistencia de UTC naive a hora local Managua (+6h).

    Los registros previos al fix se guardaban restando 6h (UTC). Se suman 6h para
    dejarlos en hora local fija de Nicaragua. Excluye los datos sembrados de julio
    (fecha <= 2026-07-13), que ya estaban en hora local. La tabla _data_migrations
    garantiza que solo se ejecute una vez por base de datos.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    MARCA = "asistencia_utc_a_local"
    with Session(engine) as db:
        try:
            db.execute(text(
                "CREATE TABLE IF NOT EXISTS _data_migrations ("
                "nombre VARCHAR(100) PRIMARY KEY, "
                "aplicado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            ))
            db.commit()
            ya_aplicada = db.execute(
                text("SELECT 1 FROM _data_migrations WHERE nombre = :n"),
                {"n": MARCA},
            ).scalar()
            if ya_aplicada:
                return
            # SQLite usa datetime(..., '+6 hours') en lugar de DATE_ADD
            if _is_sqlite():
                resultado = db.execute(text(
                    "UPDATE asistencias SET "
                    "hora_entrada_real = datetime(hora_entrada_real, '+6 hours'), "
                    "hora_salida_real = datetime(hora_salida_real, '+6 hours'), "
                    "ultimo_heartbeat = datetime(ultimo_heartbeat, '+6 hours'), "
                    "fecha = date(hora_entrada_real) "
                    "WHERE fecha > '2026-07-13'"
                ))
                db.execute(
                    text("INSERT OR IGNORE INTO _data_migrations (nombre) VALUES (:n)"),
                    {"n": MARCA},
                )
            else:
                resultado = db.execute(text(
                    "UPDATE asistencias SET "
                    "hora_entrada_real = hora_entrada_real + INTERVAL '6 hours', "
                    "hora_salida_real = hora_salida_real + INTERVAL '6 hours', "
                    "ultimo_heartbeat = ultimo_heartbeat + INTERVAL '6 hours', "
                    "fecha = CAST(hora_entrada_real AS DATE) "
                    "WHERE fecha > '2026-07-13'"
                ))
                db.execute(
                    text(
                        "INSERT INTO _data_migrations (nombre) VALUES (:n) "
                        "ON CONFLICT (nombre) DO NOTHING"
                    ),
                    {"n": MARCA},
                )
            db.commit()
            print(f"  [~] Asistencias UTC→local: {resultado.rowcount} registros corregidos (+6h)")
        except Exception as e:
            db.rollback()
            print(f"  [X] Error en migración de asistencias UTC→local: {e}")


def _migrate_asistencias_anulada():
    """Agrega la columna anulada a asistencias si no existe."""
    _add_column_if_not_exists("asistencias", "anulada",
        "ALTER TABLE asistencias ADD COLUMN anulada BOOLEAN NOT NULL DEFAULT FALSE")
    _add_column_if_not_exists("asistencias", "ultimo_heartbeat",
        "ALTER TABLE asistencias ADD COLUMN ultimo_heartbeat TIMESTAMP NULL")
    _add_column_if_not_exists("asistencias", "horas_extras_originales",
        "ALTER TABLE asistencias ADD COLUMN horas_extras_originales NUMERIC(6,2) NULL")
    _add_column_if_not_exists("asistencias", "motivo_modificacion",
        "ALTER TABLE asistencias ADD COLUMN motivo_modificacion VARCHAR(255) NULL")
    _add_column_if_not_exists("asistencias", "modificado_por",
        "ALTER TABLE asistencias ADD COLUMN modificado_por INT NULL")


def _migrate_calendario_columnas():
    """Agrega columnas faltantes a eventos_calendario si no existen.

    Bases de datos antiguas pudieron crearse antes de que el modelo incluyera
    estas columnas; el calendario selecciona la entidad completa y fallaría
    con un 500 si alguna falta.
    """
    _add_column_if_not_exists("eventos_calendario", "completado_en",
        "ALTER TABLE eventos_calendario ADD COLUMN completado_en TIMESTAMP NULL")
    _add_column_if_not_exists("eventos_calendario", "cantidad_esperada",
        "ALTER TABLE eventos_calendario ADD COLUMN cantidad_esperada NUMERIC(12,2) NULL")


def _migrate_usuarios_turno_habilitado():
    """Agrega la columna turno_habilitado a usuarios si no existe.

    Solo en la primera ejecución habilita a los Vendedores ya registrados
    (turno_habilitado = 1) para que el despliegue no los bloquee de golpe;
    en reinicios posteriores la columna ya existe y no se toca el estado.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    if _column_exists("usuarios", "turno_habilitado"):
        print("  [~] Columna 'turno_habilitado' ya existe en usuarios")
        return
    with Session(engine) as db:
        try:
            db.execute(text(
                "ALTER TABLE usuarios ADD COLUMN turno_habilitado BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            db.execute(text(
                "UPDATE usuarios SET turno_habilitado = 1 WHERE rol = 'Vendedor'"
            ))
            db.commit()
            print(
                "  [~] Columna 'turno_habilitado' agregada a usuarios y "
                "Vendedores existentes habilitados"
            )
        except Exception as e:
            db.rollback()
            print(f"  [X] Error al agregar 'turno_habilitado' a usuarios: {e}")


def _migrate_usuarios_avisos_fuera_de_turno():
    """Agrega la columna avisos_fuera_de_turno a usuarios si no existe.

    Permite recibir las notificaciones push (avisos de comandas) incluso
    cuando el usuario está "fuera del sistema" (turno cerrado, app
    cerrada o sin sesión iniciada). Por defecto queda activada para que los
    avisos siempre lleguen al dispositivo suscrito.
    """
    _add_column_if_not_exists("usuarios", "avisos_fuera_de_turno",
        "ALTER TABLE usuarios ADD COLUMN avisos_fuera_de_turno BOOLEAN NOT NULL DEFAULT TRUE")


def _migrate_usuarios_avisos_comandas():
    """Agrega los interruptores de avisos por tipo de comanda.

    ``avisos_cocina``       recibe las comandas nuevas (antes era exclusivo
                            del puesto de cocina).
    ``avisos_mesero``       recibe sus propias comandas cuando están listas.
    ``avisos_mesero_todas`` recibe también las comandas de otros meseros.

    La primera vez que se crean las columnas se respeta el comportamiento
    anterior: los puestos de cocina quedan suscritos a las comandas nuevas y
    todos quedan suscritos a las suyas. En arranques posteriores no se toca
    ninguna preferencia.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models.personal import Empleado, Puesto, Usuario
    from app.services.push_service import es_puesto_cocina

    nueva = not _column_exists("usuarios", "avisos_cocina")

    _add_column_if_not_exists("usuarios", "avisos_cocina",
        "ALTER TABLE usuarios ADD COLUMN avisos_cocina BOOLEAN NOT NULL DEFAULT FALSE")
    _add_column_if_not_exists("usuarios", "avisos_mesero",
        "ALTER TABLE usuarios ADD COLUMN avisos_mesero BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column_if_not_exists("usuarios", "avisos_mesero_todas",
        "ALTER TABLE usuarios ADD COLUMN avisos_mesero_todas BOOLEAN NOT NULL DEFAULT FALSE")

    if not nueva:
        return

    with Session(engine) as db:
        try:
            usuarios = db.execute(
                select(Usuario)
                .join(Empleado, Usuario.empleado_id == Empleado.id)
                .join(Puesto, Empleado.puesto_id == Puesto.id)
            ).scalars().all()
            suscritos = 0
            for usuario in usuarios:
                puesto = usuario.empleado.puesto if usuario.empleado else None
                if es_puesto_cocina(puesto.nombre if puesto else None):
                    usuario.avisos_cocina = True
                    suscritos += 1
            db.commit()
            print(f"  [~] Avisos de cocina activados para {suscritos} usuario(s) de cocina")
        except Exception as e:
            db.rollback()
            print(f"  [X] Error preparando los avisos de comandas: {e}")


def _migrate_mesas_apodo():
    """Agrega la columna apodo a mesas si no existe (apodo temporal de cliente)."""
    _add_column_if_not_exists("mesas", "apodo",
        "ALTER TABLE mesas ADD COLUMN apodo VARCHAR(100) NULL")


def _migrate_nombres_archivados():
    """Libera nombres retenidos por registros inactivos/eliminados.

    - Platillos inactivos (``disponible = False``):
        * Sin ventas → se eliminan físicamente (receta incluida vía cascada).
        * Con ventas → se renombran a ``{nombre}_deleted_{id}`` liberando el
          nombre original para un plato nuevo.
    - Usuarios inactivos (``activo = False``):
        * Se renombran username y la cédula de su empleado vinculado a
          ``{valor}_deleted_{id}``. En la migración NUNCA se borran usuarios:
          el borrado físico solo ocurre vía DELETE /personal/usuarios/{id}.

    Idempotente: los registros que ya tienen el sufijo ``_deleted_{id}`` se
    omiten, por lo que en reinicios posteriores el costo es mínimo.
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import Session

    from app.models.menu import MenuItem
    from app.models.orden import DetalleOrden
    from app.models.personal import Usuario, Empleado

    with Session(engine) as db:
        # --- Platillos inactivos -------------------------------------------------
        items = db.execute(
            select(MenuItem).where(MenuItem.disponible == False)  # noqa: E712
        ).scalars().all()
        for item in items:
            try:
                ventas = db.execute(
                    select(func.count())
                    .select_from(DetalleOrden)
                    .where(DetalleOrden.producto_id == item.id)
                ).scalar_one()
                if ventas == 0:
                    db.delete(item)
                    db.commit()
                    print(
                        "  [~] Platillo inactivo "
                        f"'#{item.id} {item.nombre}' eliminado (sin ventas)"
                    )
                else:
                    sufijo = f"_deleted_{item.id}"
                    if not item.nombre.endswith(sufijo):
                        nombre_archivo = (
                            f"{item.nombre[: 100 - len(sufijo)]}{sufijo}"
                        )
                        item.nombre = nombre_archivo
                        db.commit()
                        print(
                            "  [~] Platillo inactivo "
                            f"'#{item.id} {nombre_archivo}' renombrado (con ventas)"
                        )
            except Exception as e:
                db.rollback()
                print(f"  [X] Migración nombre plato #{item.id}: {e}")

        # --- Usuarios inactivos ---------------------------------------------------
        usuarios = db.execute(
            select(Usuario).where(Usuario.activo == False)  # noqa: E712
        ).scalars().all()
        for usuario in usuarios:
            try:
                sufijo = f"_deleted_{usuario.id}"
                if not usuario.username.endswith(sufijo):
                    usuario.username = (
                        f"{usuario.username[: 50 - len(sufijo)].strip()}{sufijo}"
                    )
                    db.commit()
                    print(
                        "  [~] Usuario inactivo "
                        f"'#{usuario.id}' renombrado a '{usuario.username}'"
                    )
                if usuario.empleado_id:
                    empleado = db.get(Empleado, usuario.empleado_id)
                    if empleado is not None and empleado.activo:
                        sufijo_emp = f"_deleted_{empleado.id}"
                        if empleado.cedula_identidad and not empleado.cedula_identidad.endswith(sufijo_emp):
                            empleado.cedula_identidad = (
                                f"{empleado.cedula_identidad[: 20 - len(sufijo_emp)].strip()}"
                                f"{sufijo_emp}"
                            )
                        empleado.activo = False
                        db.commit()
                        print(
                            "  [~] Empleado vinculado al usuario "
                            f"'#{usuario.id}' desactivado (cédula liberada si aplicaba)"
                        )
            except Exception as e:
                db.rollback()
                print(f"  [X] Migración nombre usuario #{usuario.id}: {e}")


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

            print("  > Tabla 'usuarios' vacia - creando administrador automatico...")

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


def _seed_harca27_admin():
    """Crea la cuenta Harca27 una sola vez cuando se configura su secreto."""
    if not settings.HARCA27_PASSWORD:
        return

    from datetime import date
    from decimal import Decimal
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.core.security import obtener_password_hash

    with Session(engine) as db:
        existente = db.execute(
            select(Usuario).where(
                func.lower(func.trim(Usuario.username)) == "harca27"
            )
        ).scalar_one_or_none()
        if existente:
            logger.info("Cuenta administradora Harca27 ya existe; no se modificó.")
            return

        cedula = "HARCA27-ADMIN"
        empleado_existente = db.execute(
            select(Empleado).where(Empleado.cedula_identidad == cedula)
        ).scalar_one_or_none()
        if empleado_existente:
            raise RuntimeError(
                "No se pudo crear Harca27: la cédula de empleado reservada ya existe."
            )

        puesto = db.execute(
            select(Puesto).where(Puesto.nombre == "Administrador")
        ).scalar_one_or_none()
        if not puesto:
            puesto = Puesto(
                nombre="Administrador",
                salario_base=Decimal("1200.00"),
            )
            db.add(puesto)
            db.flush()

        empleado = Empleado(
            cedula_identidad=cedula,
            nombre="Harca",
            apellido="27",
            puesto_id=puesto.id,
            salario_base=puesto.salario_base,
            fecha_ingreso=date.today(),
            activo=True,
        )
        db.add(empleado)
        db.flush()

        usuario = Usuario(
            username="Harca27",
            password_hash=obtener_password_hash(settings.HARCA27_PASSWORD),
            rol="Administrador",
            empleado_id=empleado.id,
            activo=True,
        )
        db.add(usuario)
        db.commit()
        logger.info("Cuenta administradora Harca27 creada.")


def _auditar_hashes():
    """Audita hashes de contraseña legacy (no-bcrypt) para diagnóstico en producción."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            rows = db.execute(
                text("SELECT username, SUBSTRING(password_hash, 1, 11) as prefix FROM usuarios")
            ).fetchall()
            problematicos = [
                row for row in rows if not (row.prefix or "").startswith("$2")
            ]
            if problematicos:
                detalle = ", ".join(
                    f"{r.username} ({r.prefix})" for r in problematicos
                )
                print(f"  [!] [AUTH AUDIT] {len(problematicos)} usuarios con hash no-bcrypt: {detalle}")
            else:
                print(f"  [AUTH AUDIT] {len(rows)} usuarios, todos con hash bcrypt válido")
        except Exception as e:
            print(f"  [!] Error en auditoría de hashes: {e}")


def _fix_orphaned_mesas():
    """Libera mesas OCUPADA que no tienen orden activa asociada."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        try:
            result = db.execute(text("""
                UPDATE mesas
                SET estado = 'LIBRE', apodo = NULL
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


def _sancar_turnos_huerfanos():
    """Cierra turnos de asistencia huérfanos (sin salida) de días anteriores.

    Reutiliza la lógica de saneamiento de ``app/db/cerrar_turnos_huerfanos.py``:
    para cada asistencia abierta cuya entrada es de un día anterior al de hoy,
    fija la salida a las 18:00 (6:00 PM) del día de la entrada, recalcula las
    horas extras (con tope de columna NUMERIC(4,2)) y deja el motivo de
    auditoría. Es idempotente: solo toca registros sin salida; los turnos de
    hoy no se modifican.
    """
    from sqlalchemy.orm import Session

    from app.db.cerrar_turnos_huerfanos import sancar_turnos_huerfanos

    with Session(engine) as db:
        try:
            cerrados = sancar_turnos_huerfanos(db)
            if cerrados:
                db.commit()
                print(
                    "  [ASISTENCIA] "
                    f"{len(cerrados)} turno(s) huérfano(s) cerrado(s) "
                    "automáticamente (salida 6:00 PM del día de entrada)"
                )
            else:
                db.rollback()
        except Exception as e:
            db.rollback()
            print(f"  [!] Error al sanear turnos huérfanos: {e}")


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


async def _camera_clip_retention_watcher():
    """Elimina clips vencidos y grabaciones abandonadas del almacenamiento persistente."""
    from sqlalchemy.orm import Session
    from app.services.camera_service import CameraService

    while True:
        try:
            with Session(engine) as db:
                CameraService(db).limpiar_clips_vencidos()
        except Exception:
            logger.exception("Falló la limpieza automática de clips de cámaras")
        await asyncio.sleep(3600)


def _generar_estudio_automatico() -> None:
    """Genera el estudio del mes anterior y avisa a administración."""
    from app.core.database import SessionLocal
    from app.models.estudio_mercado import EstadoEstudio
    from app.services.estudio_mercado_service import EstudioMercadoService
    from app.services.push_service import PushService

    with SessionLocal() as db:
        servicio = EstudioMercadoService(db)
        estudio = servicio.generar_automatico()
        if estudio is None or estudio.notificado:
            return
        push = PushService(db)
        if estudio.estado == EstadoEstudio.COMPLETADO:
            push.notificar_estudio_mercado(estudio)
        else:
            push.notificar_estudio_mercado_error(estudio)
        estudio.notificado = True
        db.commit()


async def _estudio_mercado_watcher():
    """Tarea en segundo plano: estudio de mercado automático mensual."""
    from app.core.tiempo import ahora_local

    while True:
        await asyncio.sleep(max(60, settings.ESTUDIO_MERCADO_INTERVALO_SEGUNDOS))
        try:
            ahora = ahora_local()
            if (
                ahora.day < settings.ESTUDIO_MERCADO_DIA
                or ahora.hour < settings.ESTUDIO_MERCADO_HORA
            ):
                continue
            if not settings.GEMINI_API_KEY:
                logger.warning(
                    "[ESTUDIO] GEMINI_API_KEY no configurada; se omite el estudio automático"
                )
                continue
            await asyncio.to_thread(_generar_estudio_automatico)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Falló la generación automática del estudio de mercado"
            )


@app.get(
    "/healthcheck",
    tags=["Sistema"],
    summary="Verificar estado del sistema"
)
def healthcheck() -> Dict[str, str]:
    """
    Endpoint de verificación de salud del sistema.

    Retorna el estado del servidor, la marca de tiempo y conectividad a BD.
    """
    from sqlalchemy import text
    from app.core.database import engine
    
    db_status = "connected"
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "disconnected"
        # Detalle del error sin exponer credenciales (útil para diagnóstico)
        import re
        msg = str(e)
        msg = re.sub(r"://[^@]*@", "://***@", msg)
        db_error = msg[:300]
    
    result = {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "service": "Sazón Caribeño API",
        "version": "1.0.0",
        "database": db_status,
        "engine": "sqlite" if _is_sqlite() else "postgresql",
    }
    if db_error:
        result["database_error"] = db_error
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
