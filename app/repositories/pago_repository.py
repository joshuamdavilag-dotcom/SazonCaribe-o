from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pago import PagoOnline


class PagoRepository:
    """Acceso a datos de los pagos en línea (PagoOnline)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_idempotencia(self, key: str) -> PagoOnline | None:
        """Busca un pago por su clave de idempotencia (evita cobros duplicados)."""
        return self.db.execute(
            select(PagoOnline).where(PagoOnline.clave_idempotencia == key)
        ).scalar_one_or_none()

    def obtener_por_referencia(
        self, referencia: str, *, bloquear: bool = False
    ) -> PagoOnline | None:
        """Busca un pago por referencia; con ``bloquear=True`` aplica ``FOR UPDATE``."""
        statement = select(PagoOnline).where(PagoOnline.referencia == referencia)
        if bloquear:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def obtener_por_evento(self, proveedor: str, evento_id: str) -> PagoOnline | None:
        """Busca un pago por el id de evento del proveedor (deduplicación de webhooks)."""
        return self.db.execute(
            select(PagoOnline).where(
                PagoOnline.proveedor == proveedor,
                PagoOnline.evento_proveedor_id == evento_id,
            )
        ).scalar_one_or_none()

    def obtener_por_orden_activa(self, orden_id: int) -> PagoOnline | None:
        """Busca el pago asociado a una orden activa, si existe."""
        return self.db.execute(
            select(PagoOnline).where(PagoOnline.orden_activa_id == orden_id)
        ).scalar_one_or_none()

    def crear(self, pago: PagoOnline) -> PagoOnline:
        """Agrega un pago a la sesión (sin commit); el llamador decide cuándo confirmar."""
        self.db.add(pago)
        return pago
