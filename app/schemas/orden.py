from datetime import datetime
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
        description="Precio unitario al momento de la venta (congelado)"
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
    mesa_id: int = Field(
        ...,
        gt=0,
        description="ID de la mesa del pedido",
        examples=[1]
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
    mesa_id: int = Field(
        ...,
        description="ID de la mesa"
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
        description="Total de la orden"
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
