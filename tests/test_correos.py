from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.config import Settings
from app.core.correos import TIPOS_CORREO
from app.core.database import Base
from app.models.correo import ConfiguracionCorreo, EnvioCorreo, EstadoEnvio
from app.schemas.correo import (
    ConfiguracionCorreoUpdate,
    DestinatarioCorreoCreate,
)
from app.services import correo_service
from app.services.correo_service import CorreoService, ErrorEnvioCorreo


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _settings(**overrides) -> Settings:
    datos = {
        "BREVO_API_KEY": "clave-de-prueba",
        "CORREO_REMITENTE": "remitente@test.com",
        "CORREO_REMITENTE_NOMBRE": "Sazón Caribeño",
        "CORREO_TIMEOUT": 1,
        "CORREO_MAX_INTENTOS": 1,
    }
    datos.update(overrides)
    return Settings(**datos)


def _servicio(db, **overrides) -> CorreoService:
    return CorreoService(db, settings=_settings(**overrides))


def _destinatario(db, email="dueno@test.com", nombre="Dueño"):
    return _servicio(db).crear_destinatario(
        DestinatarioCorreoCreate(nombre=nombre, email=email)
    )


def test_sembrar_configuracion_es_idempotente():
    db = _session()
    try:
        servicio = _servicio(db)
        assert servicio.sembrar_configuracion() == len(TIPOS_CORREO)
        assert servicio.sembrar_configuracion() == 0
        configs = db.execute(select(ConfiguracionCorreo)).scalars().all()
        assert len(configs) == len(TIPOS_CORREO)
        assert all(config.activo is False for config in configs)
    finally:
        db.close()


def test_destinatarios_validan_formato_y_duplicados():
    db = _session()
    try:
        servicio = _servicio(db)
        with pytest.raises(HTTPException) as error:
            servicio.crear_destinatario(
                DestinatarioCorreoCreate(nombre="Malo", email="sin-arroba")
            )
        assert error.value.status_code == 400

        _destinatario(db, email="Dueno@Test.com")
        with pytest.raises(HTTPException) as error:
            servicio.crear_destinatario(
                DestinatarioCorreoCreate(nombre="Otro", email="dueno@test.com")
            )
        assert error.value.status_code == 400
    finally:
        db.close()


def test_vista_previa_solo_incluye_secciones_seleccionadas():
    db = _session()
    try:
        servicio = _servicio(db)
        destinatario = _destinatario(db)
        servicio.guardar_configuracion(
            "manual",
            ConfiguracionCorreoUpdate(
                secciones=["ventas"], destinatario_ids=[destinatario.id]
            ),
        )
        resolucion = servicio._resolver_envio(
            "manual", ["ventas"], None, None, None, None, None, usar_config=True
        )
        html = resolucion["html"]
        assert "Resumen de ventas" in html
        assert "Platillos más vendidos" not in html
        assert "Nómina pagada" not in html
    finally:
        db.close()


def test_seccion_no_disponible_devuelve_400():
    db = _session()
    try:
        servicio = _servicio(db)
        destinatario = _destinatario(db)
        with pytest.raises(HTTPException) as error:
            servicio.guardar_configuracion(
                "stock_bajo",
                ConfiguracionCorreoUpdate(
                    secciones=["nomina"], destinatario_ids=[destinatario.id]
                ),
            )
        assert error.value.status_code == 400
    finally:
        db.close()


def test_tipo_desconocido_devuelve_400():
    db = _session()
    try:
        servicio = _servicio(db)
        with pytest.raises(HTTPException) as error:
            servicio.guardar_configuracion("inventado", ConfiguracionCorreoUpdate())
        assert error.value.status_code == 400
    finally:
        db.close()


def test_sin_destinatarios_no_envia():
    db = _session()
    try:
        servicio = _servicio(db)
        with pytest.raises(HTTPException) as error:
            servicio.enviar_ahora("manual", ["ventas"], None)
        assert error.value.status_code == 400
        assert "destinatarios" in error.value.detail.lower()
    finally:
        db.close()


def test_fallo_brevo_registra_error(monkeypatch):
    db = _session()
    try:
        servicio = _servicio(db)
        destinatario = _destinatario(db)

        def _fallar(*args, **kwargs):
            raise ErrorEnvioCorreo("Brevo caído")

        monkeypatch.setattr(servicio, "_enviar_brevo", _fallar)
        envio = servicio.enviar_ahora(
            "manual", ["ventas"], [destinatario.id]
        )

        assert envio.estado == EstadoEnvio.ERROR.value
        assert "Brevo caído" in (envio.error or "")
        guardado = db.get(EnvioCorreo, envio.id)
        assert guardado.estado == EstadoEnvio.ERROR.value
    finally:
        db.close()


def test_programado_encola_una_sola_vez_por_semana(monkeypatch):
    db = _session()
    try:
        servicio = _servicio(db)
        destinatario = _destinatario(db)
        servicio.guardar_configuracion(
            "resumen_semanal",
            ConfiguracionCorreoUpdate(
                activo=True, hora=8, destinatario_ids=[destinatario.id]
            ),
        )
        lunes = datetime(2026, 10, 26, 9, 0, 0)
        monkeypatch.setattr(correo_service, "ahora_local", lambda: lunes)

        assert servicio.evaluar_programados() == 1
        assert servicio.evaluar_programados() == 0

        pendientes = db.execute(
            select(EnvioCorreo).where(
                EnvioCorreo.estado == EstadoEnvio.PENDIENTE.value
            )
        ).scalars().all()
        assert len(pendientes) == 1
        assert pendientes[0].tipo == "resumen_semanal"
    finally:
        db.close()


def test_programado_no_corre_antes_de_la_hora(monkeypatch):
    db = _session()
    try:
        servicio = _servicio(db)
        destinatario = _destinatario(db)
        servicio.guardar_configuracion(
            "resumen_semanal",
            ConfiguracionCorreoUpdate(
                activo=True, hora=8, destinatario_ids=[destinatario.id]
            ),
        )
        lunes_temprano = datetime(2026, 10, 26, 6, 30, 0)
        monkeypatch.setattr(correo_service, "ahora_local", lambda: lunes_temprano)

        assert servicio.evaluar_programados() == 0
    finally:
        db.close()


def test_sin_configuracion_reporta_no_habilitado():
    db = _session()
    try:
        servicio = _servicio(db, BREVO_API_KEY="", CORREO_REMITENTE="")
        estado = servicio.estado()
        assert estado["habilitado"] is False
        assert "BREVO_API_KEY" in estado["mensaje"]
    finally:
        db.close()
