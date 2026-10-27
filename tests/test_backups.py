import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.models.auditoria import RegistroAuditoria
from app.models.backup import BackupSistema
from app.services.backup_service import BackupService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _auditoria(marcador: str) -> RegistroAuditoria:
    return RegistroAuditoria(
        ocurrido_en=datetime(2026, 10, 27, 12, 0, 0),
        actor_id=1,
        actor_username="admin",
        actor_rol="Administrador",
        accion="PRUEBA",
        entidad_tipo="TEST",
        entidad_id=None,
        descripcion=marcador,
        antes={"payload": "x" * 200_000},
    )


def test_backup_guarda_contenido_mayor_a_64kb():
    """MySQL TEXT corta en 64 KB; el volcado real supera ese tamaño."""
    db = _session()
    try:
        db.add(_auditoria("marcador-grande"))
        db.commit()

        servicio = BackupService()
        resultado = servicio.crear_backup_bd(db)

        registro = db.get(BackupSistema, resultado["id"])
        assert registro is not None
        assert registro.tamano_bytes > 65_535
        assert len(registro.contenido.encode("utf-8")) > 65_535

        payload = json.loads(registro.contenido)
        assert "backups_sistema" not in payload["datos"]
        assert payload["datos"]["registros_auditoria"][0]["descripcion"] == "marcador-grande"
    finally:
        db.close()


def test_backup_se_puede_restaurar():
    db = _session()
    try:
        db.add(_auditoria("estado-original"))
        db.commit()
        servicio = BackupService()
        servicio.crear_backup_bd(db)

        db.query(RegistroAuditoria).delete()
        db.add(_auditoria("estado-modificado"))
        db.commit()

        listado = servicio.listar_backups_bd(db)
        assert listado
        registro = db.get(BackupSistema, listado[0]["id"])
        payload = json.loads(registro.contenido)

        resultado = servicio.restaurar_backup_bd(db, payload)

        assert resultado["registros"] >= 1
        descripciones = [r.descripcion for r in db.query(RegistroAuditoria).all()]
        assert "estado-original" in descripciones
        assert "estado-modificado" not in descripciones
    finally:
        db.close()
