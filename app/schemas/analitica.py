from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ProductoEstrellaResponse(BaseModel):
    """Esquema de respuesta para el producto más vendido del período."""
    model_config = ConfigDict(from_attributes=True)

    producto_id: int = Field(
        ...,
        description="ID del producto más vendido"
    )
    nombre: str = Field(
        ...,
        description="Nombre del producto"
    )
    cantidad_vendida: int = Field(
        ...,
        description="Unidades vendidas del producto en el período"
    )


class CierreCajaResponse(BaseModel):
    """Esquema de respuesta para el cierre de caja diario."""
    model_config = ConfigDict(from_attributes=True)

    fecha: date = Field(
        ...,
        description="Fecha del cierre de caja"
    )
    total_ventas: float = Field(
        ...,
        description="Suma total de dinero recaudado en órdenes pagadas"
    )
    ordenes_pagadas_count: int = Field(
        ...,
        description="Cantidad de órdenes pagadas (facturas cobradas)"
    )
    ordenes_canceladas_count: int = Field(
        ...,
        description="Cantidad de órdenes canceladas (auditoría de pérdidas)"
    )
    producto_estrella: Optional[ProductoEstrellaResponse] = Field(
        default=None,
        description="Producto más vendido del día (None si no hubo ventas)"
    )
