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
    apodo: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Apodo temporal de la mesa (ej: nombre del cliente que ocupó la mesa)"
    )
    grupo_fusion_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Identificador del grupo de fusión (None si la mesa no está fusionada)"
    )
    color_fusion: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Color hexadecimal que distingue al grupo de fusión"
    )
    mesa_principal_id: Optional[int] = Field(
        default=None,
        description="ID de la mesa principal del grupo de fusión (None si es la principal o no está fusionada)"
    )


class FusionMesasRequest(BaseModel):
    """Esquema para fusionar dos o más mesas en un mismo grupo."""

    mesa_ids: List[int] = Field(
        ...,
        min_length=2,
        description="IDs de las mesas a fusionar (al menos dos)",
        examples=[[1, 2]]
    )
    color: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Color hexadecimal opcional para el grupo; si se omite se asigna uno libre"
    )


class FusionMesasResponse(BaseModel):
    """Resultado de fusionar o separar mesas."""

    grupo_fusion_id: Optional[str] = None
    color_fusion: Optional[str] = None
    mesa_principal_id: Optional[int] = None
    orden_id: Optional[int] = None
    mesas: List[MesaResponse] = Field(default_factory=list)
    mensaje: str = ""


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
