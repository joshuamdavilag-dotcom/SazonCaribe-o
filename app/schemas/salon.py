from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Enum de Estado de Mesa
# =============================================================================

class EstadoMesa(str, Enum):
    """Estados posibles para una mesa del restaurante."""
    LIBRE = "LIBRE"
    OCUPADA = "OCUPADA"
    RESERVADA = "RESERVADA"
    MANTENIMIENTO = "MANTENIMIENTO"


# =============================================================================
# Mesa Schemas
# =============================================================================

class MesaBase(BaseModel):
    """Esquema base para Mesa."""
    numero: int = Field(
        ...,
        gt=0,
        description="Número identificador de la mesa",
        examples=[1]
    )
    capacidad: int = Field(
        default=4,
        gt=0,
        description="Número de comensales que puede albergar",
        examples=[4]
    )
    estado: EstadoMesa = Field(
        default=EstadoMesa.LIBRE,
        description="Estado actual de la mesa",
        examples=[EstadoMesa.LIBRE]
    )


class MesaCreate(MesaBase):
    """Esquema para crear una Mesa."""
    zona_id: int = Field(
        ...,
        gt=0,
        description="ID de la zona donde se ubica la mesa",
        examples=[1]
    )


class MesaUpdate(BaseModel):
    """Esquema para actualizar una Mesa."""
    numero: Optional[int] = Field(default=None, gt=0)
    capacidad: Optional[int] = Field(default=None, gt=0)
    estado: Optional[EstadoMesa] = None
    zona_id: Optional[int] = Field(default=None, gt=0)


class MesaResponse(MesaBase):
    """Esquema de respuesta para Mesa."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la mesa"
    )
    zona_id: int = Field(
        ...,
        description="ID de la zona asociada"
    )


# =============================================================================
# Zona Schemas
# =============================================================================

class ZonaBase(BaseModel):
    """Esquema base para Zona del restaurante."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nombre de la zona",
        examples=["Terraza"]
    )
    descripcion: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Descripción de la zona",
        examples=["Área al aire libre con vista al mar"]
    )


class ZonaCreate(ZonaBase):
    """Esquema para crear una Zona."""
    pass


class ZonaResponse(ZonaBase):
    """Esquema de respuesta para Zona."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la zona"
    )
    mesas: List[MesaResponse] = Field(
        default_factory=list,
        description="Lista de mesas en la zona"
    )
