from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.orden import EstadoOrden


# =============================================================================
# DetalleOrden Schemas
# =============================================================================

class DetalleOrdenCreate(BaseModel):
    """Esquema para crear un detalle de orden (ítem del pedido)."""
    producto_id: int = Field(
        ...,
        gt=0,
        description="ID del producto del menú",
        examples=[1]
    )
    cantidad: int = Field(
        ...,
        gt=0,
        description="Cantidad del producto (debe ser mayor que 0)",
        examples=[2]
    )
    notas: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Notas especiales (ej: sin cebolla, poco cocido)",
        examples=["Sin cebolla, té frío sin hielo"]
    )


class DetalleOrdenResponse(BaseModel):
    """Esquema de respuesta para DetalleOrden."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del detalle"
    )
    orden_id: int = Field(
        ...,
        description="ID de la orden asociada"
    )
    producto_id: int = Field(
        ...,
        description="ID del producto del menú"
    )
    producto_nombre: str = Field(
        default="",
        description="Nombre del producto (eager-loaded)"
    )
    cantidad: int = Field(
        ...,
        description="Cantidad ordenada"
    )
    precio_unitario: Decimal = Field(
        ...,
        decimal_places=2,
        description="Precio unitario base al momento de la venta (congelado)"
    )
    descuento_porcentaje: Optional[Decimal] = Field(
        default=None,
        decimal_places=2,
        description="Porcentaje de descuento aplicado (ej: 15.00 = 15%)"
    )
    descuento_monto: Optional[Decimal] = Field(
        default=None,
        decimal_places=2,
        description="Monto fijo de descuento aplicado"
    )
    motivo_descuento: Optional[str] = Field(
        default=None,
        description="Motivo del descuento (ej: Cliente frecuente, Promoción)"
    )
    notas: Optional[str] = Field(
        default=None,
        description="Notas especiales del ítem"
    )

    @model_validator(mode='before')
    @classmethod
    def _fill_nombre(cls, data):
        if not isinstance(data, dict):
            nombre = getattr(data, 'producto_nombre', '') or ''
            if not nombre:
                producto = getattr(data, 'producto', None)
                if producto is not None:
                    setattr(data, 'producto_nombre', producto.nombre)
        return data


# =============================================================================
# Orden Schemas
# =============================================================================

class OrdenCreate(BaseModel):
    """Esquema para crear una nueva orden/pedido."""
    mesa_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la mesa del pedido (null para llevar / venta directa)",
        examples=[1]
    )
    nombre_cliente: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nombre del cliente (para llevar)",
    )
    detalles: List[DetalleOrdenCreate] = Field(
        ...,
        min_length=1,
        description="Lista de ítems del pedido (al menos uno)",
        examples=[[
            {"producto_id": 1, "cantidad": 2},
            {"producto_id": 3, "cantidad": 1, "notas": "Sin picante"}
        ]]
    )


class OrdenResponse(BaseModel):
    """Esquema de respuesta para Orden."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la orden"
    )
    mesa_id: Optional[int] = Field(
        default=None,
        description="ID de la mesa (null para venta directa / para llevar)",
    )
    mesero_id: int = Field(
        ...,
        description="ID del mesero que tomó la orden"
    )
    estado: EstadoOrden = Field(
        ...,
        description="Estado actual de la orden"
    )
    total: Decimal = Field(
        ...,
        decimal_places=2,
        description="Total final de la orden (subtotal - descuentos)"
    )
    subtotal: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Suma de precios antes de descuentos"
    )
    descuento_total: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Monto total descontado"
    )
    nombre_cliente: Optional[str] = Field(
        default=None,
        description="Nombre del cliente (para llevar)"
    )
    fecha_creacion: datetime = Field(
        ...,
        description="Fecha y hora de creación de la orden"
    )
    detalles: List[DetalleOrdenResponse] = Field(
        default_factory=list,
        description="Lista de ítems de la orden"
    )


class AgregarDetallesOrden(BaseModel):
    """Esquema para agregar ítems a una orden existente."""
    detalles: List[DetalleOrdenCreate] = Field(
        ...,
        min_length=1,
        description="Lista de nuevos ítems a agregar a la orden",
    )


class ActualizarEstadoOrden(BaseModel):
    """Esquema simple para actualizar el estado de una orden."""
    estado: EstadoOrden = Field(
        ...,
        description="Nuevo estado de la orden",
        examples=[EstadoOrden.PREPARANDO]
    )


class AgregarItemsOrdenRequest(BaseModel):
    """Esquema canónico para agregar ítems a una orden existente."""
    items: List[DetalleOrdenCreate] = Field(
        ...,
        min_length=1,
        description="Lista de nuevos ítems a agregar a la orden",
    )


class VentaRetroactivaCreate(BaseModel):
    """Esquema para registrar una venta de días pasados."""
    fecha: date = Field(
        ...,
        description="Fecha de la venta (YYYY-MM-DD)",
    )
    mesa_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la mesa (null para venta directa / para llevar)",
    )
    nombre_cliente: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nombre del cliente (para llevar)",
    )
    detalles: List[DetalleOrdenCreate] = Field(
        ...,
        min_length=1,
        description="Lista de ítems vendidos (al menos uno)",
    )


class AplicarDescuentoItemRequest(BaseModel):
    """Esquema para aplicar descuento a un ítem específico de la orden."""
    detalle_id: int = Field(
        ...,
        gt=0,
        description="ID del DetalleOrden a descontar",
    )
    tipo: str = Field(
        ...,
        pattern="^(porcentaje|monto)$",
        description="Tipo de descuento: 'porcentaje' o 'monto'",
        examples=["porcentaje"],
    )
    valor: float = Field(
        ...,
        gt=0,
        description="Valor del descuento (ej: 15 para 15% o 50.00 para C$50)",
    )
    motivo: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Motivo del descuento (ej: Cliente frecuente, Promoción)",
    )


class AplicarDescuentoGlobalRequest(BaseModel):
    """Esquema para aplicar descuento global a toda la orden."""
    tipo: str = Field(
        ...,
        pattern="^(porcentaje|monto)$",
        description="Tipo de descuento: 'porcentaje' o 'monto'",
        examples=["porcentaje"],
    )
    valor: float = Field(
        ...,
        gt=0,
        description="Valor del descuento global (ej: 10 para 10% o 100.00 para C$100)",
    )
    motivo: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Motivo del descuento global",
    )
