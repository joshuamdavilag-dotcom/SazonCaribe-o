from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoriaMenuPublicaResponse(BaseModel):
    """Esquema de respuesta público para una Categoría del Menú.

    Solo datos de exhibición para la futura carta digital. No incluye
    información administrativa.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la categoría"
    )
    nombre: str = Field(
        ...,
        description="Nombre de la categoría"
    )
    descripcion: Optional[str] = Field(
        default=None,
        description="Descripción de la categoría"
    )


class MenuItemPublicoResponse(BaseModel):
    """Esquema de respuesta público para un plato del menú.

    Exclusivamente datos de exhibición para la futura carta digital.
    NO incluye recetas, insumos, costos ni inventario interno.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del plato"
    )
    nombre: str = Field(
        ...,
        description="Nombre del plato"
    )
    descripcion: Optional[str] = Field(
        default=None,
        description="Descripción del plato"
    )
    precio: Decimal = Field(
        ...,
        decimal_places=2,
        description="Precio de venta al cliente"
    )
    disponible: bool = Field(
        ...,
        description="Disponibilidad del plato en el menú"
    )
    imagen_url: Optional[str] = Field(
        default=None,
        description="Ruta de la imagen del plato. Si es null, la carta usa un placeholder local."
    )
    tiempo_preparacion: Optional[int] = Field(
        default=None,
        description="Tiempo estimado de preparación en minutos (opcional)"
    )
    categoria: Optional[CategoriaMenuPublicaResponse] = Field(
        default=None,
        description="Categoría asociada"
    )
