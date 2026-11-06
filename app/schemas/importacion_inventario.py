from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _valor_enum(valor):
    return getattr(valor, "value", valor)


class DetalleImportacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fila: int
    texto_origen: Optional[str] = None
    nombre_detectado: str
    cantidad: Decimal
    unidad_texto: Optional[str] = None
    precio_unitario: Optional[Decimal] = None
    precio_total: Optional[Decimal] = None
    categoria_texto: Optional[str] = None
    insumo_id: Optional[int] = None
    insumo_nombre: Optional[str] = None
    accion: str
    categoria_id: Optional[int] = None
    categoria_nombre: Optional[str] = None
    unidad_medida_id: Optional[int] = None
    unidad_medida_nombre: Optional[str] = None
    unidad_empaque_id: Optional[int] = None
    unidad_empaque_nombre: Optional[str] = None
    factor_empaque: Optional[float] = None
    stock_minimo: Optional[Decimal] = None
    confianza: Optional[float] = None
    notas: Optional[str] = None
    aplicado: bool = False

    @field_validator("accion", mode="before")
    @classmethod
    def _normalizar_accion(cls, valor):
        return _valor_enum(valor)


class ImportacionInventarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_archivo: str
    tipo_archivo: str
    estado: str
    modelo_ia: Optional[str] = None
    resumen: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    creada_en: datetime
    aplicada_en: Optional[datetime] = None
    detalles: List[DetalleImportacionResponse] = Field(default_factory=list)

    @field_validator("estado", mode="before")
    @classmethod
    def _normalizar_estado(cls, valor):
        return _valor_enum(valor)


class ImportacionInventarioResumenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_archivo: str
    tipo_archivo: str
    estado: str
    modelo_ia: Optional[str] = None
    resumen: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    creada_en: datetime
    aplicada_en: Optional[datetime] = None

    @field_validator("estado", mode="before")
    @classmethod
    def _normalizar_estado(cls, valor):
        return _valor_enum(valor)


class DetalleImportacionAplicar(BaseModel):
    id: int = Field(..., gt=0)
    accion: str = Field(..., pattern=r"^(CREAR|ACTUALIZAR|OMITIR)$")
    nombre: str = Field(default="", max_length=100)
    cantidad: Decimal = Field(..., ge=0, decimal_places=2)
    unidad_medida_id: Optional[int] = Field(default=None, gt=0)
    unidad_empaque_id: Optional[int] = Field(default=None, gt=0)
    unidad_empaque_nombre: Optional[str] = Field(default=None, max_length=50)
    factor_empaque: Optional[float] = Field(default=None, gt=0)
    precio_unitario: Optional[Decimal] = Field(default=None, ge=0)
    precio_total: Optional[Decimal] = Field(default=None, ge=0)
    categoria_id: Optional[int] = Field(default=None, gt=0)
    categoria_nombre: Optional[str] = Field(default=None, max_length=50)
    stock_minimo: Optional[Decimal] = Field(default=None, gt=0)


class ImportacionAplicarRequest(BaseModel):
    detalles: List[DetalleImportacionAplicar] = Field(..., min_length=1)


class ImportacionAplicarResponse(BaseModel):
    importacion_id: int
    creadas: int
    actualizadas: int
    omitidas: int
    total_movimientos: int
    resumen: dict[str, Any]
