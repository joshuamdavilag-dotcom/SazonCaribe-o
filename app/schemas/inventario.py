from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


# =============================================================================
# Categoría Insumo Schemas
# =============================================================================

class CategoriaInsumoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50, description="Nombre de la categoría")


class CategoriaInsumoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID único de la categoría")
    nombre: str = Field(..., description="Nombre de la categoría")


# =============================================================================
# Unidad de Medida Schemas
# =============================================================================

class UnidadMedidaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50, description="Nombre de la unidad")
    abreviatura: str = Field(..., min_length=1, max_length=10, description="Abreviatura")


class UnidadMedidaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID único de la unidad")
    nombre: str = Field(..., description="Nombre de la unidad")
    abreviatura: str = Field(..., description="Abreviatura de la unidad")


# =============================================================================
# Proveedor Schemas
# =============================================================================

class ProveedorCreate(BaseModel):
    """Esquema para crear un Proveedor."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del proveedor",
        examples=["Distribuidora Mariscos del Caribe"]
    )
    contacto_nombre: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nombre del vendedor o contacto directo",
        examples=["Carlos Mendoza"]
    )
    telefono: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Número de teléfono del proveedor",
        examples=["+58 412-1234567"]
    )
    email: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Correo electrónico del proveedor",
        examples=["ventas@mariscoscaribe.com"]
    )


class ProveedorResponse(BaseModel):
    """Esquema de respuesta para Proveedor."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del proveedor"
    )
    nombre: str = Field(
        ...,
        description="Nombre del proveedor"
    )
    contacto_nombre: Optional[str] = Field(
        default=None,
        description="Nombre del vendedor o contacto"
    )
    telefono: Optional[str] = Field(
        default=None,
        description="Número de teléfono"
    )
    email: Optional[str] = Field(
        default=None,
        description="Correo electrónico"
    )


# =============================================================================
# Ingrediente Schemas
# =============================================================================

class IngredienteCreate(BaseModel):
    """Esquema para crear un Ingrediente."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre único del ingrediente",
        examples=["Camarón"]
    )
    unidad_medida: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unidad de medida (Kg, Litros, Unidades, etc.)",
        examples=["Kg"]
    )
    stock_minimo: Decimal = Field(
        default=Decimal("5.00"),
        gt=0,
        decimal_places=2,
        description="Stock mínimo para alertas de reabastecimiento",
        examples=[5.00]
    )
    costo_unitario: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        decimal_places=2,
        description="Costo por unidad de medida del ingrediente",
        examples=[2500.00]
    )
    proveedor_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID del proveedor principal (opcional)",
        examples=[1]
    )


class IngredienteResponse(BaseModel):
    """Esquema de respuesta para Ingrediente."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del ingrediente"
    )
    nombre: str = Field(
        ...,
        description="Nombre del ingrediente"
    )
    unidad_medida: str = Field(
        ...,
        description="Unidad de medida"
    )
    stock_actual: Decimal = Field(
        ...,
        decimal_places=2,
        description="Stock actual en inventario"
    )
    stock_minimo: Decimal = Field(
        ...,
        decimal_places=2,
        description="Stock mínimo para alertas"
    )
    costo_unitario: Decimal = Field(
        ...,
        decimal_places=2,
        description="Costo por unidad de medida del ingrediente"
    )
    proveedor_id: Optional[int] = Field(
        default=None,
        description="ID del proveedor principal"
    )
    proveedor: Optional[ProveedorResponse] = Field(
        default=None,
        description="Información del proveedor asociado"
    )


# =============================================================================
# Insumo Schemas
# =============================================================================

class InsumoCreate(BaseModel):
    """Esquema para crear un Insumo."""
    nombre: str = Field(
        ..., min_length=1, max_length=100,
        description="Nombre único del insumo",
        examples=["Servilletas"]
    )
    cantidad_actual: Decimal = Field(
        default=Decimal("0.00"), ge=0, decimal_places=2,
        description="Cantidad actual en inventario",
        examples=[100.00]
    )
    unidad_medida_id: int = Field(
        ..., gt=0,
        description="ID de la unidad de medida",
        examples=[1]
    )
    categoria_id: Optional[int] = Field(
        default=None, gt=0,
        description="ID de la categoría del insumo (opcional)",
        examples=[1]
    )
    stock_minimo: Decimal = Field(
        default=Decimal("5.00"), gt=0, decimal_places=2,
        description="Stock mínimo para alertas de reabastecimiento",
        examples=[10.00]
    )


class InsumoResponse(BaseModel):
    """Esquema de respuesta para Insumo."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID único del insumo")
    nombre: str = Field(..., description="Nombre del insumo")
    cantidad_actual: Decimal = Field(..., decimal_places=2, description="Cantidad actual en inventario")
    unidad_medida: str = Field(..., description="Nombre de la unidad de medida")
    unidad_medida_id: int = Field(..., description="ID de la unidad de medida")
    categoria_id: Optional[int] = Field(default=None, description="ID de la categoría")
    categoria_nombre: Optional[str] = Field(default=None, description="Nombre de la categoría")
    stock_minimo: Decimal = Field(..., decimal_places=2, description="Stock mínimo para alertas")
    costo_unitario: Decimal = Field(default=Decimal("0.00"), decimal_places=2, description="Costo por unidad de medida")

    @model_validator(mode="before")
    @classmethod
    def _populate_virtual_fields(cls, data):
        obj = data
        um = getattr(obj, "unidad_medida_obj", None) or getattr(obj, "unidad_medida", None)
        if hasattr(um, "nombre"):
            setattr(obj, "unidad_medida", um.nombre)
            setattr(obj, "unidad_medida_id", um.id)
        elif isinstance(um, str):
            setattr(obj, "unidad_medida", um)
            if not hasattr(obj, "unidad_medida_id") or getattr(obj, "unidad_medida_id", None) is None:
                setattr(obj, "unidad_medida_id", 0)
        cat = getattr(obj, "categoria", None)
        if hasattr(cat, "nombre"):
            setattr(obj, "categoria_nombre", cat.nombre)
            setattr(obj, "categoria_id", cat.id)
        elif cat is None:
            setattr(obj, "categoria_nombre", None)
        return obj


# =============================================================================
# MovimientoInventario Schemas
# =============================================================================

class MovimientoCreate(BaseModel):
    """Esquema para registrar un Movimiento de Inventario."""
    insumo_id: int = Field(
        ...,
        gt=0,
        description="ID del insumo",
        examples=[1]
    )
    tipo: str = Field(
        ...,
        pattern=r"^(ENTRADA|SALIDA)$",
        description="Tipo de movimiento: ENTRADA o SALIDA",
        examples=["ENTRADA"]
    )
    cantidad: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Cantidad del movimiento (debe ser mayor a 0)",
        examples=[10.50]
    )
    motivo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Motivo del movimiento",
        examples=["Compra a proveedor"]
    )


class MovimientoResponse(BaseModel):
    """Esquema de respuesta para Movimiento de Inventario."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del movimiento"
    )
    insumo_id: int = Field(
        ...,
        description="ID del insumo"
    )
    tipo: str = Field(
        ...,
        description="Tipo de movimiento (ENTRADA/SALIDA)"
    )
    cantidad: Decimal = Field(
        ...,
        decimal_places=2,
        description="Cantidad del movimiento"
    )
    motivo: str = Field(
        ...,
        description="Motivo del movimiento"
    )
    fecha: datetime = Field(
        ...,
        description="Fecha y hora del movimiento"
    )
    insumo: Optional[InsumoResponse] = Field(
        default=None,
        description="Información del insumo asociado"
    )


class ActualizarStockInsumo(BaseModel):
    """Esquema para actualizar el stock de un insumo (PATCH)."""
    cantidad: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Cantidad a agregar (entrada) o restar (salida)",
        examples=[25.00]
    )
    tipo: str = Field(
        ...,
        pattern=r"^(ENTRADA|SALIDA)$",
        description="Tipo de ajuste: ENTRADA (proveedor) o SALIDA (consumo)",
        examples=["ENTRADA"]
    )
    motivo: str = Field(
        default="Ajuste de inventario",
        min_length=1,
        max_length=100,
        description="Motivo del ajuste",
        examples=["Compra a proveedor"]
    )


class InsumoUpdate(BaseModel):
    """Esquema para actualizar los detalles de un insumo (PATCH)."""
    categoria_id: Optional[int] = Field(
        default=None, gt=0,
        description="ID de la categoría del insumo"
    )
    unidad_medida_id: Optional[int] = Field(
        default=None, gt=0,
        description="ID de la unidad de medida"
    )
    stock_minimo: Optional[Decimal] = Field(
        default=None, gt=0, decimal_places=2,
        description="Stock mínimo para alertas"
    )
