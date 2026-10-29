import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.permisos import (
    CLAVES_PERMISOS,
    PERMISOS_CRITICOS,
    permisos_efectivos,
    permisos_por_defecto,
    tiene_permiso,
)
from app.models.personal import Usuario
from app.schemas.permiso import ActualizarPermisosRequest
from app.services.permiso_service import PermisoService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _usuario(db, username, rol, empleado_id, permisos=None):
    usuario = Usuario(
        username=username,
        password_hash="x",
        rol=rol,
        empleado_id=empleado_id,
        activo=True,
        turno_habilitado=True,
        permisos=permisos,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_defaults_reproducen_el_rbac_actual():
    assert set(permisos_por_defecto("Administrador")) == set(CLAVES_PERMISOS)
    gerente = set(permisos_por_defecto("Gerente"))
    assert "backups_gestionar" not in gerente
    assert "personal_gestionar" in gerente
    assert "menu_gestionar" in gerente
    assert permisos_por_defecto("Vendedor") == []


def test_overrides_conceden_y_revocan():
    db = _session()
    try:
        vendedor = _usuario(db, "mesero1", "Vendedor", 1, {"menu_gestionar": True})
        assert tiene_permiso(vendedor, "menu_gestionar") is True
        assert tiene_permiso(vendedor, "gastos_gestionar") is False

        gerente = _usuario(db, "gerente1", "Gerente", 2, {"gastos_gestionar": False})
        assert tiene_permiso(gerente, "gastos_gestionar") is False
        assert tiene_permiso(gerente, "menu_gestionar") is True
    finally:
        db.close()


def test_administrador_siempre_conserva_todo():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1, {"menu_gestionar": False})
        assert set(permisos_efectivos(admin)) == set(CLAVES_PERMISOS)
        assert tiene_permiso(admin, "menu_gestionar") is True
    finally:
        db.close()


def test_no_puede_editar_permisos_del_administrador():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        gerente = _usuario(db, "gerente1", "Gerente", 2)
        servicio = PermisoService(db)
        with pytest.raises(HTTPException) as exc:
            servicio.actualizar(
                admin.id,
                ActualizarPermisosRequest(permisos=[]),
                gerente,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()


def test_no_puede_editar_sus_propios_permisos():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        servicio = PermisoService(db)
        with pytest.raises(HTTPException) as exc:
            servicio.actualizar(
                admin.id,
                ActualizarPermisosRequest(permisos=[]),
                admin,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()


def test_gerente_no_puede_cambiar_permisos_criticos():
    db = _session()
    try:
        gerente = _usuario(db, "gerente1", "Gerente", 1)
        vendedor = _usuario(db, "mesero1", "Vendedor", 2)
        servicio = PermisoService(db)
        actuales = permisos_efectivos(vendedor)
        with pytest.raises(HTTPException) as exc:
            servicio.actualizar(
                vendedor.id,
                ActualizarPermisosRequest(
                    permisos=actuales + ["auditoria_ver"]
                ),
                gerente,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()


def test_administrador_concede_permiso_critico_sin_guardar_lo_que_igual_al_rol():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        vendedor = _usuario(db, "mesero1", "Vendedor", 2)
        servicio = PermisoService(db)
        respuesta = servicio.actualizar(
            vendedor.id,
            ActualizarPermisosRequest(
                permisos=["menu_gestionar", "auditoria_ver"]
            ),
            admin,
        )
        assert respuesta.puede_editar is True
        claves = {p.clave for p in respuesta.permisos if p.concedido}
        assert claves == {"menu_gestionar", "auditoria_ver"}

        db.refresh(vendedor)
        assert vendedor.permisos == {"menu_gestionar": True, "auditoria_ver": True}

        servicio.actualizar(
            vendedor.id,
            ActualizarPermisosRequest(permisos=["menu_gestionar"]),
            admin,
        )
        db.refresh(vendedor)
        assert vendedor.permisos == {"menu_gestionar": True}
    finally:
        db.close()


def test_restablecer_al_rol_borra_overrides():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        gerente = _usuario(db, "gerente1", "Gerente", 2, {"gastos_gestionar": False})
        servicio = PermisoService(db)
        servicio.actualizar(
            gerente.id,
            ActualizarPermisosRequest(permisos=permisos_por_defecto("Gerente")),
            admin,
        )
        db.refresh(gerente)
        assert gerente.permisos is None
    finally:
        db.close()


def test_rechaza_claves_desconocidas():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        vendedor = _usuario(db, "mesero1", "Vendedor", 2)
        servicio = PermisoService(db)
        with pytest.raises(HTTPException) as exc:
            servicio.actualizar(
                vendedor.id,
                ActualizarPermisosRequest(permisos=["no_existe"]),
                admin,
            )
        assert exc.value.status_code == 400
    finally:
        db.close()


def test_catalogo_expone_todos_los_grupos():
    db = _session()
    try:
        admin = _usuario(db, "admin1", "Administrador", 1)
        catalogo = PermisoService(db).catalogo(admin)
        assert len(catalogo.permisos) == len(CLAVES_PERMISOS)
        assert len(catalogo.grupos) == 5
        criticos = {p.clave for p in catalogo.permisos if p.critico}
        assert criticos == set(PERMISOS_CRITICOS)
    finally:
        db.close()
