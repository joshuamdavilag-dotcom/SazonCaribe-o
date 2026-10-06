from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.pago import EstadoPago


class PagoOnlineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    orden_id: int
    proveedor: str
    referencia: str
    estado: EstadoPago
    monto: Decimal
    monto_confirmado: Decimal | None
    moneda: str
    moneda_confirmada: str | None
    checkout_url: str | None
    creado_en: datetime


class DisponibilidadPagosResponse(BaseModel):
    proveedor_configurado: str
    adaptador_disponible: bool
    habilitado: bool
    mensaje: str


class CheckoutSessionResponse(BaseModel):
    pago: PagoOnlineResponse
