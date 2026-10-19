from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pago import PagoOnline


class PagoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_idempotencia(self, key: str) -> PagoOnline | None:
        return self.db.execute(
            select(PagoOnline).where(PagoOnline.clave_idempotencia == key)
        ).scalar_one_or_none()

    def obtener_por_referencia(
        self, referencia: str, *, bloquear: bool = False
    ) -> PagoOnline | None:
        statement = select(PagoOnline).where(PagoOnline.referencia == referencia)
        if bloquear:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalar_one_or_none()

    def obtener_por_evento(self, proveedor: str, evento_id: str) -> PagoOnline | None:
        return self.db.execute(
            select(PagoOnline).where(
                PagoOnline.proveedor == proveedor,
                PagoOnline.evento_proveedor_id == evento_id,
            )
        ).scalar_one_or_none()

    def obtener_por_orden_activa(self, orden_id: int) -> PagoOnline | None:
        return self.db.execute(
            select(PagoOnline).where(PagoOnline.orden_activa_id == orden_id)
        ).scalar_one_or_none()

    def crear(self, pago: PagoOnline) -> PagoOnline:
        self.db.add(pago)
        return pago
