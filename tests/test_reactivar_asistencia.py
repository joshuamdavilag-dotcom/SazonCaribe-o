from datetime import date, datetime, time
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.database import Base
from app.models.asistencia import Asistencia, Turno
from app.models.auditoria import RegistroAuditoria
from app.models.personal import Empleado, Puesto, Usuario
from app.schemas.asistencia import AsistenciaReactivarRequest
from app.services.asistencia_service import AsistenciaService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _escenario(db):
    puesto = Puesto(nombre="Mesero", salario_base=Decimal("8000.00"))
    db.add(puesto)
    db.commit()

    empleado = Empleado(
        nombre="Ana",
        apellido="López",
        puesto_id=puesto.id,
        salario_base=Decimal("8000.00"),
        activo=True,
    )
    db.add(empleado)
    db.commit()

    actor = Usuario(
        username="gerente.prueba",
        password_hash="x",
        rol="Gerente",
        empleado_id=empleado.id,
        activo=True,
        turno_habilitado=True,
    )
    db.add(actor)
    db.commit()
    db.refresh(actor)

    turno = Turno(
        nombre="Matutino",
        hora_entrada=time(8, 0),
        hora_salida=time(16, 0),
        horas_teoricas=8,
    )
    db.add(turno)
    db.commit()

    asistencia = Asistencia(
        empleado_id=empleado.id,
        turno_id=turno.id,
        fecha=date(2026, 11, 10),
        hora_entrada_real=datetime(2026, 11, 10, 8, 0),
        hora_salida_real=datetime(2026, 11, 10, 8, 0),
        horas_extras=Decimal("1.50"),
        observaciones="Cierre automático por deshabilitación de turno",
    )
    db.add(asistencia)
    db.commit()
    db.refresh(asistencia)
    return empleado, actor, turno, asistencia


def test_reactivar_reabre_el_turno_y_audita():
    db = _session()
    try:
        _, actor, _, asistencia = _escenario(db)

        resultado = AsistenciaService(db).reactivar_asistencia(
            asistencia.id,
            AsistenciaReactivarRequest(motivo="El turno se cerró por doble toque"),
            actor,
        )

        assert resultado.hora_salida_real is None
        assert resultado.horas_extras == Decimal("0.00")
        assert resultado.observaciones is None
        assert resultado.modificado_por == actor.id
        assert resultado.motivo_modificacion == "El turno se cerró por doble toque"

        evento = db.execute(
            select(RegistroAuditoria).where(
                RegistroAuditoria.accion == "ASISTENCIA_REACTIVADA"
            )
        ).scalars().first()
        assert evento is not None
        assert evento.entidad_id == asistencia.id
        assert evento.antes["estado"] == "cerrado"
        assert evento.despues["estado"] == "abierto"
    finally:
        db.close()


def test_no_reactiva_un_registro_anulado():
    db = _session()
    try:
        _, actor, _, asistencia = _escenario(db)
        asistencia.anulada = True
        db.commit()

        with pytest.raises(HTTPException) as exc:
            AsistenciaService(db).reactivar_asistencia(
                asistencia.id,
                AsistenciaReactivarRequest(motivo="Prueba"),
                actor,
            )
        assert exc.value.status_code == 400
        assert "anulado" in exc.value.detail.lower()
    finally:
        db.close()


def test_no_reactiva_un_turno_que_sigue_activo():
    db = _session()
    try:
        _, actor, _, asistencia = _escenario(db)
        asistencia.hora_salida_real = None
        db.commit()

        with pytest.raises(HTTPException) as exc:
            AsistenciaService(db).reactivar_asistencia(
                asistencia.id,
                AsistenciaReactivarRequest(motivo="Prueba"),
                actor,
            )
        assert exc.value.status_code == 400
        assert "activo" in exc.value.detail.lower()
    finally:
        db.close()


def test_no_reactiva_si_el_empleado_ya_tiene_otro_turno_abierto():
    db = _session()
    try:
        empleado, actor, turno, asistencia = _escenario(db)
        db.add(
            Asistencia(
                empleado_id=empleado.id,
                turno_id=turno.id,
                fecha=date(2026, 11, 11),
                hora_entrada_real=datetime(2026, 11, 11, 8, 0),
                hora_salida_real=None,
                horas_extras=Decimal("0.00"),
            )
        )
        db.commit()

        with pytest.raises(HTTPException) as exc:
            AsistenciaService(db).reactivar_asistencia(
                asistencia.id,
                AsistenciaReactivarRequest(motivo="Prueba"),
                actor,
            )
        assert exc.value.status_code == 400
        assert "turno abierto" in exc.value.detail.lower()
    finally:
        db.close()


def test_reactivar_exige_motivo():
    db = _session()
    try:
        _, actor, _, asistencia = _escenario(db)

        with pytest.raises(HTTPException) as exc:
            AsistenciaService(db).reactivar_asistencia(
                asistencia.id,
                AsistenciaReactivarRequest(motivo="   "),
                actor,
            )
        assert exc.value.status_code == 400
        assert "motivo" in exc.value.detail.lower()
    finally:
        db.close()
