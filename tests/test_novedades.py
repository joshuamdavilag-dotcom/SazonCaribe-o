from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.novedades import NOVEDADES
from app.models.novedad import NovedadSistema
from app.services import push_service
from app.services.novedad_service import NovedadService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_sembrar_es_idempotente():
    db = _session()
    try:
        servicio = NovedadService(db)
        creadas = servicio.sembrar()
        assert creadas == len(NOVEDADES)
        assert servicio.sembrar() == 0
        total = db.execute(select(NovedadSistema)).scalars().all()
        assert len(total) == len(NOVEDADES)
    finally:
        db.close()


def test_listar_devuelve_la_mas_reciente_primero():
    db = _session()
    try:
        servicio = NovedadService(db)
        servicio.sembrar()
        novedades = servicio.listar()
        assert novedades[0].version == "1.2.0"
        assert servicio.ultima().version == "1.2.0"
    finally:
        db.close()


def test_notificar_pendientes_marca_todas_y_envia_solo_la_ultima(monkeypatch):
    db = _session()
    enviadas = []

    def _falso(self, novedad):
        enviadas.append(novedad.version)
        return 1

    monkeypatch.setattr(push_service.PushService, "notificar_novedad", _falso)
    try:
        servicio = NovedadService(db)
        servicio.sembrar()
        assert len(servicio.pendientes_de_aviso()) == len(NOVEDADES)

        enviados = servicio.notificar_pendientes()
        assert enviados == 1
        assert enviadas == ["1.2.0"]
        assert servicio.pendientes_de_aviso() == []

        for novedad in servicio.listar():
            assert novedad.notificada is True
            assert novedad.notificada_en is not None
    finally:
        db.close()


def test_notificar_pendientes_sin_novedades_no_envia(monkeypatch):
    db = _session()
    llamado = []

    def _falso(self, novedad):  # pragma: no cover - no debe ejecutarse
        llamado.append(novedad)
        return 1

    monkeypatch.setattr(push_service.PushService, "notificar_novedad", _falso)
    try:
        assert NovedadService(db).notificar_pendientes() == 0
        assert llamado == []
    finally:
        db.close()
