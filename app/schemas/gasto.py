from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.gasto import CategoriaGasto


class GastoCreate(BaseModel):
    """Esquema para registrar un gasto operativo manual."""
    concepto: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Concepto o descripción del gasto",
        examples=["Servicio de reparación de freidora"],
    )
    monto: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Monto del gasto (debe ser mayor a 0)",
        examples=[3500.00],
    )
    categoria: CategoriaGasto = Field(
        default=CategoriaGasto.OPERATIVO,
        description="Categoría del gasto",
    )
    insumo_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID del insumo asociado (para gastos generados por SALIDA de inventario)",
    )


class GastoResponse(BaseModel):
    """Esquema de respuesta para un gasto."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del gasto",
    )
    concepto: str = Field(
        ...,
        description="Concepto del gasto",
    )
    monto: Decimal = Field(
        ...,
        decimal_places=2,
        description="Monto del gasto",
    )
    categoria: CategoriaGasto = Field(
        ...,
        description="Categoría del gasto",
    )
    fecha: datetime = Field(
        ...,
        description="Fecha y hora del registro",
    )
    registrado_por: Optional[int] = Field(
        default=None,
        description="ID del usuario que registró el gasto",
    )
    insumo_id: Optional[int] = Field(
        default=None,
        description="ID del insumo asociado",
    )
