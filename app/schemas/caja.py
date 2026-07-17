from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class CierreCajaResponse(BaseModel):
    """Esquema de respuesta para un cierre de caja."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ..., description="ID único del cierre de caja"
    )
    fecha_cierre: datetime = Field(
        ..., description="Fecha y hora del cierre"
    )
    total_ventas: float = Field(
        ..., description="Suma de totales de las órdenes archivadas"
    )
    total_ordenes: int = Field(
        ..., description="Cantidad de órdenes archivadas"
    )
    cerrado_por: Optional[int] = Field(
        default=None, description="ID del usuario que realizó el cierre"
    )


class HistorialDiarioResponse(BaseModel):
    """Resumen del historial del día actual."""
    model_config = ConfigDict(from_attributes=True)

    fecha: str = Field(
        ..., description="Fecha del historial (YYYY-MM-DD)"
    )
    total_ventas: float = Field(
        ..., description="Suma de totales de órdenes pagadas sin archivar"
    )
    total_ordenes: int = Field(
        ..., description="Cantidad de órdenes pagadas sin archivar"
    )
    ordenes: list = Field(
        default_factory=list,
        description="Lista de órdenes pagadas del día",
    )
