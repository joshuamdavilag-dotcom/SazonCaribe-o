from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.models.auditoria import RegistroAuditoria
from app.models.caja import CierreCaja
from app.models.configuracion import ConfiguracionSistema
from app.models.gasto import CategoriaGasto, Gasto
from app.services.caja_service import CajaService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _gasto(concepto: str = "Luz") -> Gasto:
    return Gasto(
        concepto=concepto,
        monto=Decimal("500.00"),
        categoria=CategoriaGasto.SERVICIOS,
        fecha=datetime(2026, 10, 27, 22, 0, 0),
    )


def test_cierre_automatico_apagado_por_defecto():
    db = _session()
    try:
        estado = CajaService(db).estado_cierre_automatico()
        assert estado.activo is False
        assert estado.proxima_ejecucion is None
    finally:
        db.close()


def test_activar_registra_fecha_para_no_cerrar_de_inmediato():
    db = _session()
    try:
        estado = CajaService(db).configurar_cierre_automatico(
            True,
            usuario_id=1,
            actor_username="admin",
            actor_rol="Administrador",
        )

        assert estado.activo is True
        assert estado.ultima_fecha is not None
        assert estado.proxima_ejecucion is not None
        assert estado.proxima_ejecucion.hour == 0

        activo = db.get(ConfiguracionSistema, CajaService.CLAVE_ACTIVO)
        assert activo.valor == "true"

        acciones = db.execute(
            select(RegistroAuditoria.accion)
        ).scalars().all()
        assert "CIERRE_AUTOMATICO_CONFIGURADO" in acciones
    finally:
        db.close()


def test_cierre_automatico_archiva_gastos_sin_ordenes():
    db = _session()
    try:
        db.add(_gasto())
        db.commit()

        servicio = CajaService(db)
        cierre = servicio.cerrar_caja_automatica()

        assert cierre is not None
        assert cierre.total_ordenes == 0
        assert cierre.total_ventas == 0
        assert cierre.cerrado_por is None

        gasto = db.execute(select(Gasto)).scalars().one()
        assert gasto.cierre_caja_id == cierre.id

        guardado = db.get(CierreCaja, cierre.id)
        assert guardado is not None

        acciones = db.execute(select(RegistroAuditoria)).scalars().all()
        evento = next(a for a in acciones if a.accion == "CIERRE_CAJA_AUTOMATICO")
        assert evento.actor_username == "sistema"
        assert evento.despues["cierre_id"] == cierre.id

        assert servicio.config.obtener(CajaService.CLAVE_ULTIMA_FECHA)
        assert servicio.config.obtener(CajaService.CLAVE_ULTIMA_EJECUCION)
    finally:
        db.close()


def test_cierre_automatico_sin_movimientos_no_crea_cierre():
    db = _session()
    try:
        cierre = CajaService(db).cerrar_caja_automatica()
        assert cierre is None
        assert db.execute(select(CierreCaja)).scalars().all() == []
    finally:
        db.close()


def test_cierre_manual_sigue_exigiendo_ordenes():
    import pytest
    from fastapi import HTTPException

    db = _session()
    try:
        db.add(_gasto())
        db.commit()

        with pytest.raises(HTTPException) as error:
            CajaService(db).cerrar_caja(usuario_id=1)

        assert error.value.status_code == 400
    finally:
        db.close()
