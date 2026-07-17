from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class PeriodoEnum(str, Enum):
    """Periodos de tiempo para reportes de cierre de caja."""
    DIARIO = "diario"
    SEMANAL = "semanal"
    QUINCENAL = "quincenal"
    MENSUAL = "mensual"


class TopPlatilloResponse(BaseModel):
    """Esquema de respuesta para un platillo en el top de ventas."""
    model_config = ConfigDict(from_attributes=True)

    producto_id: int = Field(
        ...,
        description="ID del producto del menú"
    )
    nombre: str = Field(
        ...,
        description="Nombre del platillo"
    )
    cantidad_vendida: int = Field(
        ...,
        description="Unidades vendidas en el periodo"
    )
    ingresos_generados: float = Field(
        ...,
        description="Ingresos totales generados por este platillo"
    )


class CierreCajaPeriodoResponse(BaseModel):
    """Esquema de respuesta para el cierre de caja por periodo."""
    model_config = ConfigDict(from_attributes=True)

    periodo: str = Field(
        ...,
        description="Tipo de periodo consultado (diario, semanal, quincenal, mensual)"
    )
    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio del rango consultado"
    )
    fecha_fin: date = Field(
        ...,
        description="Fecha de fin del rango consultado"
    )
    ingresos_totales: float = Field(
        ...,
        description="Suma de todas las ventas pagadas y cerradas en el periodo"
    )
    gastos_nomina: float = Field(
        ...,
        description="Suma proporcional de salarios y horas extras devengados en el periodo"
    )
    costo_insumos: float = Field(
        ...,
        description="Costo total de ingredientes utilizados en recetas vendidas"
    )
    gastos_operativos: float = Field(
        ...,
        description="Gastos operativos registrados en el periodo (suministros, mantenimiento, etc.)"
    )
    utilidad_neta: float = Field(
        ...,
        description="Ingresos Totales - (Gastos de Nómina + Costo de Insumos + Gastos Operativos)"
    )
    ordenes_pagadas: int = Field(
        ...,
        description="Cantidad de órdenes pagadas en el periodo"
    )
    ordenes_canceladas: int = Field(
        ...,
        description="Cantidad de órdenes canceladas en el periodo"
    )
    top_platillos: List[TopPlatilloResponse] = Field(
        default_factory=list,
        description="Los 5 platillos más vendidos en el periodo"
    )
