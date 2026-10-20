from datetime import date, datetime
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
    fecha: Optional[date] = Field(
        default=None,
        description="Fecha del gasto (YYYY-MM-DD). Si no se envía, usa la fecha actual.",
    )


class GastoUpdate(BaseModel):
    """Esquema para editar un gasto existente (requiere motivo obligatorio)."""
    concepto: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nuevo concepto del gasto",
    )
    monto: Optional[Decimal] = Field(
        default=None,
        gt=0,
        decimal_places=2,
        description="Nuevo monto del gasto (debe ser mayor a 0)",
    )
    categoria: Optional[CategoriaGasto] = Field(
        default=None,
        description="Nueva categoría del gasto",
    )
    fecha: Optional[date] = Field(
        default=None,
        description="Nueva fecha del gasto (YYYY-MM-DD)",
    )
    motivo: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Motivo obligatorio de la modificación (queda en auditoría)",
        examples=["Monto mal tecleado al registrar"],
    )


class GastoEliminarRequest(BaseModel):
    """Esquema para eliminar (borrado lógico) un gasto con motivo obligatorio."""
    motivo: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Motivo obligatorio de la eliminación (queda en auditoría)",
        examples=["Gasto duplicado por error"],
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
    cierre_caja_id: Optional[int] = Field(
        default=None,
        description="ID del cierre de caja que archivó este gasto",
    )
    eliminado: bool = Field(
        default=False,
        description="Indica si el gasto fue eliminado (borrado lógico)",
    )
    motivo_eliminacion: Optional[str] = Field(
        default=None,
        description="Motivo por el que se eliminó el gasto",
    )
    eliminado_por: Optional[int] = Field(
        default=None,
        description="ID del usuario que eliminó el gasto",
    )
    eliminado_en: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora de la eliminación",
    )
