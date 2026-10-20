from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.descuento import TipoDescuento


class DescuentoFrecuenteCreate(BaseModel):
    """Esquema para crear un descuento predeterminado del catálogo."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del descuento (ej: Empleado, Promo Martes)",
        examples=["Empleado"],
    )
    tipo: TipoDescuento = Field(
        default=TipoDescuento.PORCENTAJE,
        description="PORCENTAJE (0-100) o MONTO (C$ fijo)",
    )
    valor: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Valor del descuento (porcentaje o monto en C$)",
        examples=[15.00],
    )

    @model_validator(mode="after")
    def validar_porcentaje(self) -> "DescuentoFrecuenteCreate":
        """Valida que el valor no supere 100 cuando el tipo es PORCENTAJE."""
        if self.tipo == TipoDescuento.PORCENTAJE and self.valor > 100:
            raise ValueError("El porcentaje no puede ser mayor a 100")
        return self


class DescuentoFrecuenteUpdate(BaseModel):
    """Esquema para actualizar un descuento predeterminado."""
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    tipo: Optional[TipoDescuento] = Field(default=None)
    valor: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    activo: Optional[bool] = Field(default=None)


class DescuentoFrecuenteResponse(BaseModel):
    """Esquema de respuesta para un descuento predeterminado."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID único del descuento")
    nombre: str = Field(..., description="Nombre del descuento")
    tipo: TipoDescuento = Field(..., description="Tipo de descuento")
    valor: Decimal = Field(..., decimal_places=2, description="Valor del descuento")
    activo: bool = Field(..., description="Si está disponible para aplicar")
