from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.inventario import InsumoResponse


# =============================================================================
# CategoríaMenu Schemas
# =============================================================================

class CategoriaMenuBase(BaseModel):
    """Esquema base para Categoría del Menú."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nombre de la categoría",
        examples=["Platos Fuertes"]
    )
    descripcion: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Descripción de la categoría",
        examples=["Platos principales del menú"]
    )


class CategoriaMenuCreate(CategoriaMenuBase):
    """Esquema para crear una Categoría del Menú."""
    pass


class CategoriaMenuResponse(CategoriaMenuBase):
    """Esquema de respuesta para Categoría del Menú."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la categoría"
    )


# =============================================================================
# Receta Schemas
# =============================================================================

class RecetaBase(BaseModel):
    """Esquema base para Receta."""
    cantidad_necesaria: Decimal = Field(
        ...,
        gt=0,
        decimal_places=3,
        description="Cantidad necesaria del ingrediente (porción exacta que gasta el plato)",
        examples=[0.150]
    )


class RecetaCreate(RecetaBase):
    """Esquema para crear una Receta."""
    insumo_id: int = Field(
        ...,
        gt=0,
        description="ID del insumo del almacén",
        examples=[1]
    )


class RecetaResponse(RecetaBase):
    """Esquema de respuesta para Receta."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la receta"
    )
    menu_item_id: int = Field(
        ...,
        description="ID del plato asociado"
    )
    insumo_id: int = Field(
        ...,
        description="ID del insumo del almacén"
    )
    insumo: Optional[InsumoResponse] = Field(
        default=None,
        description="Detalles del insumo asociado"
    )


# =============================================================================
# MenuItem Schemas
# =============================================================================

class MenuItemBase(BaseModel):
    """Esquema base para Item del Menú."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del plato",
        examples=["Arroz con Camarón"]
    )
    descripcion: Optional[str] = Field(
        default=None,
        description="Descripción del plato",
        examples=["Arroz marinero con camarones frescos del Caribe"]
    )
    precio: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Precio de venta al cliente",
        examples=[15.99]
    )
    disponible: bool = Field(
        default=True,
        description="Disponibilidad del plato en el menú"
    )


class MenuItemCreate(MenuItemBase):
    """Esquema para crear un Item del Menú con su receta."""
    categoria_id: int = Field(
        ...,
        gt=0,
        description="ID de la categoría del menú",
        examples=[1]
    )
    receta: List[RecetaCreate] = Field(
        default_factory=list,
        description="Lista de ingredientes del plato (receta)",
        examples=[[{"insumo_id": 1, "cantidad_necesaria": 0.150}]]
    )


class MenuItemResponse(MenuItemBase):
    """Esquema de respuesta para Item del Menú."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del plato"
    )
    categoria_id: int = Field(
        ...,
        description="ID de la categoría asociada"
    )
    categoria: Optional[CategoriaMenuResponse] = Field(
        default=None,
        description="Detalles de la categoría asociada"
    )
    ingredientes_receta: List[RecetaResponse] = Field(
        default_factory=list,
        description="Lista de ingredientes del plato (receta)"
    )


class MenuItemUpdate(BaseModel):
    """Esquema para actualizar un Item del Menú (PUT)."""
    nombre: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nombre del plato",
        examples=["Arroz con Camarón Especial"]
    )
    descripcion: Optional[str] = Field(
        default=None,
        description="Descripción del plato",
        examples=["Arroz marinero con camarones frescos y coco"]
    )
    precio: Optional[Decimal] = Field(
        default=None,
        gt=0,
        decimal_places=2,
        description="Precio de venta al cliente",
        examples=[18.99]
    )
    disponible: Optional[bool] = Field(
        default=None,
        description="Disponibilidad del plato en el menú"
    )
    categoria_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la nueva categoría del menú",
        examples=[2]
    )
    ingredientes_receta: Optional[List[RecetaCreate]] = Field(
        default=None,
        description="Lista completa de ingredientes del plato (reemplaza la existente)",
        examples=[[{"insumo_id": 1, "cantidad_necesaria": 0.200}]]
    )
