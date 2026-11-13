"""Pruebas del borrado de registros de auditoría (solo Administrador)."""

from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas)
from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.auditoria import RegistroAuditoria
from app.models.personal import Usuario
from app.services.auditoria_service import AuditoriaService


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


def _usuario(db, username, rol):
    usuario = Usuario(
        username=username,
        password_hash="x",
        rol=rol,
        empleado_id=1,
        activo=True,
        turno_habilitado=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _registro(db, usuario, accion="GASTO_EDITADO"):
    registro = RegistroAuditoria(
        actor_id=usuario.id,
        actor_username=usuario.username,
        actor_rol=usuario.rol,
        accion=accion,
        entidad_tipo="gasto",
        entidad_id=7,
        descripcion="Dato corrupto que gerencia pidió sacar",
        antes={"monto": 100},
        despues={"monto": 200},
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def test_elimina_el_registro_y_deja_resumen_sin_contenido(db):
    admin = _usuario(db, "admin-aud", "Administrador")
    registro = _registro(db, admin)

    resultado = AuditoriaService(db).eliminar_registro(
        registro.id, "Datos corruptos", admin
    )

    assert resultado.eliminado is True
    assert resultado.accion_eliminada == "GASTO_EDITADO"
    assert resultado.motivo == "Datos corruptos"

    db.expire_all()
    assert db.get(RegistroAuditoria, registro.id) is None

    resumen = db.scalars(
        select(RegistroAuditoria).where(
            RegistroAuditoria.accion == "AUDITORIA_ELIMINADA"
        )
    ).one()
    assert resumen.entidad_tipo == "auditoria"
    assert resumen.entidad_id == registro.id
    assert "Datos corruptos" in resumen.descripcion
    assert resumen.antes["accion"] == "GASTO_EDITADO"
    assert resumen.antes["actor_username"] == admin.username
    assert "monto" not in resumen.antes
    assert resumen.despues == {"eliminado": True, "motivo": "Datos corruptos"}


def test_falla_si_el_registro_no_existe(db):
    admin = _usuario(db, "admin-aud", "Administrador")

    with pytest.raises(HTTPException) as error:
        AuditoriaService(db).eliminar_registro(999, "Motivo", admin)

    assert error.value.status_code == 404


def test_exige_motivo(db):
    admin = _usuario(db, "admin-aud", "Administrador")
    registro = _registro(db, admin)

    with pytest.raises(HTTPException) as error:
        AuditoriaService(db).eliminar_registro(registro.id, "   ", admin)

    assert error.value.status_code == 400
    db.expire_all()
    assert db.get(RegistroAuditoria, registro.id) is not None


def _cliente(db, usuario):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: usuario
    return TestClient(app)


def test_endpoint_borra_para_administrador(db):
    admin = _usuario(db, "admin-aud", "Administrador")
    registro = _registro(db, admin)

    try:
        respuesta = _cliente(db, admin).request(
            "DELETE",
            f"/api/v1/auditoria/{registro.id}",
            json={"motivo": "Limpieza solicitada"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert respuesta.status_code == 200
    assert respuesta.json()["eliminado"] is True
    db.expire_all()
    assert db.get(RegistroAuditoria, registro.id) is None


@pytest.mark.parametrize("rol", ["Gerente", "Vendedor"])
def test_endpoint_rechaza_a_quien_no_es_administrador(db, rol):
    usuario = _usuario(db, f"usuario-{rol.lower()}", rol)
    registro = _registro(db, usuario)

    try:
        respuesta = _cliente(db, usuario).request(
            "DELETE",
            f"/api/v1/auditoria/{registro.id}",
            json={"motivo": "Intento sin permiso"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert respuesta.status_code == 403
    db.expire_all()
    assert db.get(RegistroAuditoria, registro.id) is not None


def test_registro_eliminado_no_aparece_en_el_listado(db):
    admin = _usuario(db, "admin-aud", "Administrador")
    registro = _registro(db, admin)
    visible = _registro(db, admin, accion="ORDEN_ANULADA")

    AuditoriaService(db).eliminar_registro(registro.id, "Datos corruptos", admin)
    pagina = AuditoriaService(db).listar(None, None, 50, 0)

    ids = [item.id for item in pagina.items]
    assert registro.id not in ids
    assert visible.id in ids
    assert any(item.accion == "AUDITORIA_ELIMINADA" for item in pagina.items)
