"""Pruebas de seguridad: autenticación, autorización y exposición de datos.

Cada prueba usa una base SQLite en memoria, nunca la base real.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas)
from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.core.security import ALGORITHM, SECRET_KEY, crear_access_token, obtener_password_hash
from app.main import app
from app.models.menu import CategoriaMenu, MenuItem
from app.models.personal import Empleado, Puesto, Usuario


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    sesion = sessionmaker(bind=engine)()
    yield sesion
    sesion.close()
    engine.dispose()


def _sembrar(db):
    puesto = Puesto(nombre="Mesero", salario_base=Decimal("1000.00"))
    db.add(puesto)
    db.flush()

    empleado_admin = Empleado(
        nombre="Admin",
        apellido="Prueba",
        puesto_id=puesto.id,
        fecha_ingreso=date(2024, 1, 1),
        salario_base=Decimal("20000.00"),
        activo=True,
    )
    empleado_vendedor = Empleado(
        nombre="Vendedor",
        apellido="Prueba",
        puesto_id=puesto.id,
        fecha_ingreso=date(2024, 1, 1),
        salario_base=Decimal("12000.00"),
        activo=True,
        telefono="8888-0000",
    )
    db.add_all([empleado_admin, empleado_vendedor])
    db.flush()

    admin = Usuario(
        username="admin-seg",
        password_hash=obtener_password_hash("ClaveSegura1"),
        rol="Administrador",
        empleado_id=empleado_admin.id,
        activo=True,
        turno_habilitado=True,
    )
    vendedor = Usuario(
        username="vendedor-seg",
        password_hash=obtener_password_hash("ClaveSegura1"),
        rol="Vendedor",
        empleado_id=empleado_vendedor.id,
        activo=True,
        turno_habilitado=True,
    )
    db.add_all([admin, vendedor])

    categoria = CategoriaMenu(nombre="Seguridad", descripcion="Categoría de prueba")
    db.add(categoria)
    db.flush()
    db.add(
        MenuItem(
            nombre="Plato de prueba",
            descripcion="Solo para pruebas",
            precio=Decimal("100.00"),
            disponible=True,
            categoria_id=categoria.id,
        )
    )
    db.commit()
    return admin, vendedor


@pytest.fixture()
def cliente(db):
    _sembrar(db)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _cabecera(usuario):
    token = crear_access_token(
        {"sub": str(usuario.id), "username": usuario.username, "rol": usuario.rol}
    )
    return {"Authorization": f"Bearer {token}"}


ENDOPOINTS_SENSIBLES = [
    "/api/v1/personal/puestos",
    "/api/v1/personal/empleados",
    "/api/v1/personal/usuarios",
    "/api/v1/personal/permisos/catalogo",
    "/api/v1/inventario/unidades-medida/convertir?cantidad=1&origen=1&destino=1",
    "/api/v1/gastos/",
    "/api/v1/auditoria/",
    "/api/v1/backups/",
    "/api/v1/reportes/cierre?periodo=MENSUAL",
    "/api/v1/nomina/pendientes",
]


@pytest.mark.parametrize("ruta", ENDOPOINTS_SENSIBLES)
def test_endpoints_sensibles_exigen_autenticacion(cliente, ruta):
    respuesta = cliente.get(ruta)
    assert respuesta.status_code in (401, 403), f"{ruta} respondió {respuesta.status_code}"


def test_personal_no_expone_datos_sin_token(cliente):
    """Un anónimo no debe ver nombres, teléfonos, salarios ni usuarios."""
    for ruta in ("/api/v1/personal/empleados", "/api/v1/personal/usuarios", "/api/v1/personal/puestos"):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 401
        assert "salario_base" not in respuesta.text
        assert "username" not in respuesta.text


def test_personal_responde_con_token_valido(cliente, db):
    admin, _ = db.query(Usuario).order_by(Usuario.id).all()
    respuesta = cliente.get("/api/v1/personal/empleados", headers=_cabecera(admin))
    assert respuesta.status_code == 200
    assert respuesta.json()


def test_token_expirado_se_rechaza(cliente):
    token = jose_jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    respuesta = cliente.get("/api/v1/ordenes/", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401


def test_token_sin_firma_se_rechaza(cliente):
    token = jose_jwt.encode({"sub": "1", "exp": 9999999999}, "clave-de-atacante", algorithm=ALGORITHM)
    respuesta = cliente.get("/api/v1/ordenes/", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401


def test_token_alg_none_se_rechaza(cliente):
    encabezado = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"
    cuerpo = "eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ"
    respuesta = cliente.get(
        "/api/v1/ordenes/", headers={"Authorization": f"Bearer {encabezado}.{cuerpo}."}
    )
    assert respuesta.status_code == 401


def test_token_con_sub_no_numerico_no_rompe_el_servidor(cliente):
    """Un 'sub' inválido debe responder 401, nunca 500."""
    token = crear_access_token({"sub": "no-es-un-id", "username": "x", "rol": "Administrador"})
    respuesta = cliente.get("/api/v1/ordenes/", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401


def test_vendedor_no_accede_a_funciones_administrativas(cliente, db):
    _, vendedor = db.query(Usuario).order_by(Usuario.id).all()
    cabecera = _cabecera(vendedor)
    for ruta in (
        "/api/v1/gastos/",
        "/api/v1/auditoria/",
        "/api/v1/backups/",
        "/api/v1/personal/permisos/catalogo",
        "/api/v1/personal/empleados/bajas",
    ):
        assert cliente.get(ruta, headers=cabecera).status_code == 403, ruta


def test_usuario_desactivado_pierde_la_sesion(cliente, db):
    _, vendedor = db.query(Usuario).order_by(Usuario.id).all()
    cabecera = _cabecera(vendedor)
    vendedor.activo = False
    db.commit()
    respuesta = cliente.get("/api/v1/ordenes/", headers=cabecera)
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "USUARIO_DESACTIVADO"


def test_vendedor_sin_turno_habilitado_no_entra(cliente, db):
    _, vendedor = db.query(Usuario).order_by(Usuario.id).all()
    cabecera = _cabecera(vendedor)
    vendedor.turno_habilitado = False
    db.commit()
    respuesta = cliente.get("/api/v1/ordenes/", headers=cabecera)
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "TURNO_DESHABILITADO"


def test_api_publica_no_expone_costos_ni_recetas(cliente):
    respuesta = cliente.get("/api/public/menu")
    assert respuesta.status_code == 200
    platos = respuesta.json()
    assert platos
    prohibidas = {
        "costo",
        "costo_unitario",
        "recetas",
        "ingredientes_receta",
        "insumos",
        "costo_total",
        "margen",
    }
    for plato in platos:
        assert not (prohibidas & set(plato)), plato


def test_no_hay_travesia_de_rutas(cliente):
    for ruta in (
        "/Templates/../app/main.py",
        "/Templates/%2e%2e/app/main.py",
        "/Templates/css/../../app/main.py",
        "/carta/../app/main.py",
    ):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 404, ruta
        assert "[core]" not in respuesta.text


def test_cabeceras_de_seguridad_presentes(cliente):
    respuesta = cliente.get("/")
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "SAMEORIGIN"
    assert respuesta.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_cors_rechaza_origenes_desconocidos(cliente):
    respuesta = cliente.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://atacante.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert respuesta.headers.get("access-control-allow-origin") is None


def test_login_no_es_vulnerable_a_inyeccion_sql(cliente):
    for usuario in ("ana' OR '1'='1", "' OR 1=1 --", "admin'--"):
        respuesta = cliente.post(
            "/api/v1/auth/login",
            json={"username": usuario, "password": "ClaveSegura1"},
        )
        assert respuesta.status_code == 401
        assert "access_token" not in respuesta.text


def test_login_rechaza_usuario_inactivo(cliente, db):
    admin, _ = db.query(Usuario).order_by(Usuario.id).all()
    admin.activo = False
    db.commit()
    respuesta = cliente.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "ClaveSegura1"},
    )
    assert respuesta.status_code == 403


def test_password_nunca_se_devuelve_en_las_respuestas(cliente, db):
    admin, _ = db.query(Usuario).order_by(Usuario.id).all()
    respuesta = cliente.get("/api/v1/personal/usuarios", headers=_cabecera(admin))
    assert "password_hash" not in respuesta.text
    assert "$2b$" not in respuesta.text


def test_backups_solo_para_administrador(cliente, db):
    admin, vendedor = db.query(Usuario).order_by(Usuario.id).all()
    assert cliente.get("/api/v1/backups/", headers=_cabecera(vendedor)).status_code == 403
    assert cliente.get("/api/v1/backups/", headers=_cabecera(admin)).status_code == 200
