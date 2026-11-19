"""
Schemas de pagos en línea.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.pago import EstadoPago
from app.models.orden import MetodoPago


class PagoOnlineResponse(BaseModel):
    """Esquema de respuesta para un pago en línea."""
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
    """Esquema de respuesta con la disponibilidad de pagos en línea."""
    proveedor_configurado: str
    adaptador_disponible: bool
    habilitado: bool
    mensaje: str


class CheckoutSessionResponse(BaseModel):
    """Esquema de respuesta con la sesión de pago creada."""
    pago: PagoOnlineResponse


class PagoItemSeleccion(BaseModel):
    """Ítem elegido para cobrar (cantidad de unidades de una línea)."""

    detalle_id: int = Field(..., gt=0)
    cantidad: int = Field(..., gt=0)


class PagoComandaCreate(BaseModel):
    """Registra un pago total, un abono, una parte o una selección de ítems."""

    metodo_pago: MetodoPago
    monto: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    detalle_id: int | None = Field(default=None, gt=0)
    cantidad: int | None = Field(default=None, gt=0)
    personas: int | None = Field(default=None, gt=0)
    parte: int | None = Field(default=None, gt=0)
    division_id: int | None = Field(default=None, gt=0)
    items: list[PagoItemSeleccion] | None = None

    @model_validator(mode="after")
    def validar_tipo_de_pago(self):
        if self.metodo_pago == MetodoPago.PAGO_EN_LINEA:
            raise ValueError("El pago en línea debe confirmarse por el proveedor.")

        if self.items:
            if self.division_id is not None or self.detalle_id is not None:
                raise ValueError(
                    "La selección de ítems no se combina con divisiones ni con un "
                    "detalle suelto."
                )
            if self.monto is not None or self.personas is not None:
                raise ValueError(
                    "La selección de ítems calcula el monto sola: no envíe monto "
                    "ni personas."
                )
            if self.cantidad is not None or self.parte is not None:
                raise ValueError(
                    "La selección de ítems indica la cantidad dentro de cada ítem."
                )
            return self

        if self.division_id is not None:
            if self.parte is None or any(
                valor is not None
                for valor in (self.monto, self.detalle_id, self.cantidad, self.personas)
            ):
                raise ValueError(
                    "Una parte existente solo requiere division_id, parte y metodo_pago."
                )
            return self

        datos_division = (self.detalle_id, self.cantidad, self.personas, self.parte)
        if any(valor is not None for valor in datos_division):
            if self.monto is not None or any(valor is None for valor in datos_division):
                raise ValueError(
                    "Para dividir un ítem indique detalle_id, cantidad, personas y parte; "
                    "no envíe monto."
                )
            return self

        if self.monto is None:
            raise ValueError("Indique el monto del pago.")
        return self


class PagoComandaResponse(BaseModel):
    id: int
    usuario_id: int | None
    cobrador: str
    metodo_pago: MetodoPago
    monto: Decimal
    creado_en: datetime
    division_id: int | None = None
    parte: int | None = None
    cantidad: int | None = None
    folio_factura: str | None = None


class ParteDivisionResponse(BaseModel):
    numero: int
    cantidad: int
    monto: Decimal
    pagada: bool


class DivisionPagoResponse(BaseModel):
    id: int
    detalle_id: int
    producto_nombre: str
    cantidad: int
    personas: int
    partes: list[ParteDivisionResponse]


class DivisionPagoPreviewRequest(BaseModel):
    detalle_id: int = Field(..., gt=0)
    cantidad: int = Field(..., gt=0)
    personas: int = Field(..., gt=0)


class DivisionPagoPreviewResponse(BaseModel):
    cantidad: int
    personas: int
    partes: list[ParteDivisionResponse]


class ItemPagoResumenResponse(BaseModel):
    detalle_id: int
    producto_nombre: str
    categoria_nombre: str | None = None
    es_bebida: bool = False
    cantidad_total: int
    cantidad_disponible: int
    monto_disponible: Decimal


class EstadoPagosOrdenResponse(BaseModel):
    orden_id: int
    total: Decimal
    pagado_total: Decimal
    saldo_pendiente: Decimal
    completada: bool
    pagos: list[PagoComandaResponse]
    items: list[ItemPagoResumenResponse]
    divisiones: list[DivisionPagoResponse]
