from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.database import Base
from app.core.security import obtener_password_hash
from app.core.tiempo import hoy_local
from app.models.personal import Empleado, Puesto, Usuario
from app.schemas.personal import EliminarEmpleadoRequest, EmpleadoUpdate
from app.services.personal_service import PersonalService


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def crear_empleado(db, nombre, activo=True):
    puesto = db.query(Puesto).filter_by(nombre="Mesero").one_or_none()
    if puesto is None:
        puesto = Puesto(nombre="Mesero", salario_base=Decimal("1000.00"))
        db.add(puesto)
        db.flush()
    empleado = Empleado(
        nombre=nombre,
        apellido="Prueba",
        puesto_id=puesto.id,
        fecha_ingreso=date(2024, 1, 15),
        salario_base=Decimal("1500.00"),
        activo=activo,
    )
    db.add(empleado)
    db.flush()
    return empleado


def test_baja_guarda_fecha_y_salario_del_momento(db):
    empleado_admin = crear_empleado(db, "Gerente")
    empleado = crear_empleado(db, "Empleado")
    admin = Usuario(
        username="gerente",
        password_hash=obtener_password_hash("clave-segura"),
        rol="Administrador",
        empleado_id=empleado_admin.id,
    )
    usuario_empleado = Usuario(
        username="empleado",
        password_hash=obtener_password_hash("clave-empleado"),
        rol="Vendedor",
        empleado_id=empleado.id,
    )
    db.add_all([admin, usuario_empleado])
    db.commit()

    resultado = PersonalService(db).dar_de_baja_empleado(
        empleado.id,
        EliminarEmpleadoRequest(password="clave-segura"),
        admin,
    )

    assert resultado.activo is False
    assert resultado.fecha_ingreso == date(2024, 1, 15)
    assert empleado.fecha_baja == hoy_local()
    assert empleado.salario_base_al_baja == Decimal("1500.00")
    assert usuario_empleado.activo is False


def test_bajas_anteriores_conservan_fecha_y_salario_desconocidos(db):
    legado = crear_empleado(db, "Baja antigua", activo=False)
    db.commit()

    resultado = PersonalService(db).listar_empleados_dados_de_baja()

    assert len(resultado) == 1
    assert resultado[0].id == legado.id
    assert resultado[0].fecha_ingreso == date(2024, 1, 15)
    assert resultado[0].fecha_baja is None
    assert resultado[0].salario_base_al_baja is None
    assert resultado[0].salario_base == Decimal("1500.00")


def test_editar_estado_a_inactivo_guarda_snapshot_salarial(db):
    empleado = crear_empleado(db, "Edición")
    db.commit()

    PersonalService(db).editar_empleado(
        empleado.id,
        EmpleadoUpdate(activo=False, salario_base=Decimal("1800.00")),
    )

    assert empleado.activo is False
    assert empleado.fecha_baja == hoy_local()
    assert empleado.salario_base_al_baja == Decimal("1800.00")


def test_archivar_usuario_guarda_snapshot_de_baja_del_empleado(db):
    empleado_admin = crear_empleado(db, "Gerente")
    empleado = crear_empleado(db, "Archivado")
    empleado.cedula_identidad = "123456789012"
    admin = Usuario(
        username="gerente",
        password_hash=obtener_password_hash("clave-segura"),
        rol="Administrador",
        empleado_id=empleado_admin.id,
    )
    usuario = Usuario(
        username="usuario-archivado",
        password_hash=obtener_password_hash("clave-empleado"),
        rol="Vendedor",
        empleado_id=empleado.id,
    )
    db.add_all([admin, usuario])
    db.commit()
    servicio = PersonalService(db)
    servicio._usuario_tiene_referencias = lambda _: True
    servicio._empleado_tiene_referencias = lambda _: True

    resultado = servicio.eliminar_usuario(
        usuario.id,
        EliminarEmpleadoRequest(password="clave-segura"),
        admin,
    )

    assert resultado["resultado"] == "archivado"
    assert empleado.activo is False
    assert empleado.fecha_baja == hoy_local()
    assert empleado.salario_base_al_baja == Decimal("1500.00")
