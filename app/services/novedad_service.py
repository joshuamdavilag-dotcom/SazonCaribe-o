from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.novedades import NOVEDADES
from app.models.novedad import NovedadSistema


def _fecha_publicacion(valor: Optional[str]) -> datetime:
    """Convierte la fecha ISO declarada en el changelog a ``datetime``."""
    if not valor:
        return datetime.now()
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return datetime.now()


class NovedadService:
    """Siembra y consulta las novedades publicadas del sistema."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def sembrar(self) -> int:
        """Inserta en la BD las novedades declaradas que todavía no existen.

        Es idempotente: se apoya en ``version`` (único). Se ejecuta en cada
        arranque, así publicar una actualización es solo agregar una entrada
        en ``app/core/novedades.py``.
        """
        existentes = set(
            self.db.execute(select(NovedadSistema.version)).scalars().all()
        )
        nuevas = 0
        for entrada in NOVEDADES:
            version = (entrada.get("version") or "").strip()
            if not version or version in existentes:
                continue
            self.db.add(
                NovedadSistema(
                    version=version,
                    titulo=(entrada.get("titulo") or "").strip(),
                    resumen=(entrada.get("resumen") or "").strip(),
                    detalle=list(entrada.get("detalle") or []),
                    publicada_en=_fecha_publicacion(entrada.get("publicada_en")),
                    notificada=False,
                )
            )
            nuevas += 1
        if nuevas:
            self.db.commit()
        return nuevas

    def listar(self, limite: int = 30) -> List[NovedadSistema]:
        """Novedades más recientes primero."""
        return list(
            self.db.execute(
                select(NovedadSistema)
                .order_by(NovedadSistema.publicada_en.desc(), NovedadSistema.id.desc())
                .limit(max(1, min(limite, 100)))
            ).scalars().all()
        )

    def ultima(self) -> Optional[NovedadSistema]:
        novedades = self.listar(1)
        return novedades[0] if novedades else None

    def pendientes_de_aviso(self) -> List[NovedadSistema]:
        """Novedades que aún no se enviaron por push a los dispositivos."""
        return list(
            self.db.execute(
                select(NovedadSistema)
                .where(NovedadSistema.notificada.is_(False))
                .order_by(NovedadSistema.publicada_en.asc())
            ).scalars().all()
        )

    def notificar_pendientes(self) -> int:
        """Envía por push las novedades sin avisar y las marca como enviadas.

        Si quedaron varias novedades sin avisar (por ejemplo la primera vez que
        se despliega esta función), solo se envía un push con la más reciente
        para no saturar al equipo; las demás quedan visibles en el historial.
        """
        from app.services.push_service import PushService

        pendientes = self.pendientes_de_aviso()
        if not pendientes:
            return 0

        push = PushService(self.db)
        enviados = push.notificar_novedad(pendientes[-1])
        ahora = datetime.now()
        for novedad in pendientes:
            novedad.notificada = True
            novedad.notificada_en = ahora
        self.db.commit()
        return enviados
