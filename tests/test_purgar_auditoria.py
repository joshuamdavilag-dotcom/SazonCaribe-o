"""Pruebas de la herramienta que archiva y elimina registros de auditoría."""

import json
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.models import Asistencia, RegistroAuditoria, Usuario
from tools import purgar_auditoria


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    fabrica = sessionmaker(bind=engine)
    monkeypatch.setattr(purgar_auditoria, "SessionLocal", fabrica)

    class Ajustes:
        DATABASE_URL = "sqlite:///:memory:"

    monkeypatch.setattr(purgar_auditoria, "get_settings", lambda: Ajustes())
    return fabrica()


def _preparar(db: sessionmaker):
    hariffc = Usuario(
        username="hariffc", password_hash="x", rol="Gerente", empleado_id=1, activo=True
    )
    otro = Usuario(
        username="joshi_0211", password_hash="x", rol="Administrador", empleado_id=2, activo=True
    )
    db.add_all([hariffc, otro])
    db.commit()

    db.add_all(
        [
            RegistroAuditoria(
                actor_id=hariffc.id,
                actor_username="hariffc",
                actor_rol="Gerente",
                accion="ASISTENCIA_REACTIVADA",
                entidad_tipo="asistencia",
                entidad_id=10,
                descripcion="Reactivó la asistencia 10",
                antes={"estado": "cerrado"},
                despues={"estado": "abierto"},
            ),
            RegistroAuditoria(
                actor_id=hariffc.id,
                actor_username="hariffc",
                actor_rol="Gerente",
                accion="TURNO_CERRADO_AUTOMATICAMENTE",
                entidad_tipo="asistencia",
                entidad_id=11,
                descripcion="Cierre automático",
            ),
            RegistroAuditoria(
                actor_id=otro.id,
                actor_username="joshi_0211",
                actor_rol="Administrador",
                accion="GASTO_EDITADO",
                entidad_tipo="gasto",
                entidad_id=5,
                descripcion="Editó un gasto",
            ),
        ]
    )
    db.add(
        Asistencia(
            empleado_id=1,
            turno_id=1,
            fecha=date(2026, 11, 2),
            hora_entrada_real=datetime(2026, 11, 2, 8, 0),
            hora_salida_real=datetime(2026, 11, 2, 17, 0),
            motivo_modificacion="Corrección de entrada",
            modificado_por=hariffc.id,
        )
    )
    db.commit()
    return hariffc, otro


def test_simulacion_no_borra_ni_escribe(session, tmp_path, capsys):
    _preparar(session)
    destino = tmp_path / "respaldo"

    codigo = purgar_auditoria.main(
        ["--usuario", "hariffc", "--salida", str(destino), "--si"]
    )

    assert codigo == 0
    assert "SIMULACIÓN" in capsys.readouterr().out
    assert not destino.with_suffix(".json").exists()
    assert len(session.scalars(select(RegistroAuditoria)).all()) == 3


def test_aplicar_archiva_y_borra_solo_lo_filtrado(session, tmp_path, capsys):
    _preparar(session)
    destino = tmp_path / "auditoria_hariffc"

    codigo = purgar_auditoria.main(
        ["--usuario", "hariffc", "--salida", str(destino), "--aplicar", "--si"]
    )

    assert codigo == 0
    datos = json.loads(destino.with_suffix(".json").read_text(encoding="utf-8"))
    assert datos["total_registros_auditoria"] == 2
    assert {fila["accion"] for fila in datos["registros_auditoria"]} == {
        "ASISTENCIA_REACTIVADA",
        "TURNO_CERRADO_AUTOMATICAMENTE",
    }
    assert datos["registros_auditoria"][0]["antes"] == {"estado": "cerrado"}
    assert destino.with_suffix(".csv").exists()

    session.expire_all()
    restantes = session.scalars(select(RegistroAuditoria)).all()
    acciones = {registro.accion for registro in restantes}
    assert "GASTO_EDITADO" in acciones
    assert "ASISTENCIA_REACTIVADA" not in acciones
    assert "AUDITORIA_PURGADA" in acciones
    assert len(restantes) == 2


def test_sin_registro_no_deja_resumen(session, tmp_path):
    _preparar(session)

    codigo = purgar_auditoria.main(
        [
            "--usuario", "hariffc",
            "--salida", str(tmp_path / "x"),
            "--aplicar",
            "--si",
            "--sin-registro",
        ]
    )

    assert codigo == 0
    session.expire_all()
    acciones = {registro.accion for registro in session.scalars(select(RegistroAuditoria)).all()}
    assert acciones == {"GASTO_EDITADO"}


def test_filtra_por_accion(session, tmp_path):
    _preparar(session)
    destino = tmp_path / "solo_reactivadas"

    codigo = purgar_auditoria.main(
        [
            "--usuario", "hariffc",
            "--accion", "ASISTENCIA_REACTIVADA",
            "--salida", str(destino),
            "--aplicar",
            "--si",
        ]
    )

    assert codigo == 0
    datos = json.loads(destino.with_suffix(".json").read_text(encoding="utf-8"))
    assert datos["total_registros_auditoria"] == 1
    session.expire_all()
    acciones = {registro.accion for registro in session.scalars(select(RegistroAuditoria)).all()}
    assert "ASISTENCIA_REACTIVADA" not in acciones
    assert "TURNO_CERRADO_AUTOMATICAMENTE" in acciones


def test_incluir_asistencias_archiva_y_limpia(session, tmp_path):
    _preparar(session)
    destino = tmp_path / "con_asistencias"

    codigo = purgar_auditoria.main(
        [
            "--usuario", "hariffc",
            "--salida", str(destino),
            "--aplicar",
            "--si",
            "--incluir-asistencias",
        ]
    )

    assert codigo == 0
    datos = json.loads(destino.with_suffix(".json").read_text(encoding="utf-8"))
    assert datos["total_asistencias"] == 1
    assert datos["asistencias"][0]["motivo_modificacion"] == "Corrección de entrada"

    session.expire_all()
    asistencia = session.scalars(select(Asistencia)).one()
    assert asistencia.motivo_modificacion is None
    assert asistencia.modificado_por is None
    assert asistencia.hora_entrada_real == datetime(2026, 11, 2, 8, 0)


def test_usuario_inexistente_no_toca_nada(session, tmp_path, capsys):
    _preparar(session)

    codigo = purgar_auditoria.main(
        ["--usuario", "nadie", "--salida", str(tmp_path / "y"), "--aplicar", "--si"]
    )

    assert codigo == 3
    assert "No existe" in capsys.readouterr().out
    session.expire_all()
    assert len(session.scalars(select(RegistroAuditoria)).all()) == 3


def test_rango_de_fechas_invertido_se_rechaza(session, tmp_path):
    _preparar(session)

    codigo = purgar_auditoria.main(
        [
            "--usuario", "hariffc",
            "--desde", "2026-11-10",
            "--hasta", "2026-11-01",
            "--salida", str(tmp_path / "z"),
        ]
    )

    assert codigo == 2
