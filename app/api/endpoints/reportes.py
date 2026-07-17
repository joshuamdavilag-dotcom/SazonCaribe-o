from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import requerir_rol
from app.core.database import get_db
from app.schemas.personal import RolEnum
from app.schemas.reportes import PeriodoEnum, CierreCajaPeriodoResponse
from app.services.reportes_service import ReportesService

router = APIRouter()


def get_reportes_service(db: Session = Depends(get_db)) -> ReportesService:
    return ReportesService(db)


@router.get(
    "/cierre",
    response_model=CierreCajaPeriodoResponse,
    summary="Cierre de Caja por periodo",
    description=(
        "Calcula métricas financieras clave (ingresos, gastos de nómina, "
        "costo de insumos, utilidad neta, top platillos) para un periodo "
        "de tiempo específico. Solo accesible por Administradores y Gerentes."
    ),
    tags=["Reportes"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def cierre_caja(
    periodo: PeriodoEnum = Query(
        ...,
        description="Periodo de tiempo: diario, semanal, quincenal o mensual",
    ),
    fecha: Optional[date] = Query(
        default=None,
        description="Fecha de referencia (default: hoy). Formato: YYYY-MM-DD",
    ),
    service: ReportesService = Depends(get_reportes_service),
) -> CierreCajaPeriodoResponse:
    """
    Genera el reporte de cierre de caja para el periodo seleccionado.

    Métricas retornadas:
    - **ingresos_totales**: Suma de órdenes pagadas en el periodo
    - **gastos_nomina**: Nóminas pagadas en el periodo (salario + horas extras)
    - **costo_insumos**: Costo de ingredientes usados en recetas vendidas
    - **utilidad_neta**: Ingresos - (Gastos Nómina + Costo Insumos)
    - **ordenes_pagadas** / **ordenes_canceladas**: Conteo por estado
    - **top_platillos**: Los 5 platos más vendidos con sus ingresos

    Rangos por periodo:
    - **diario**: Solo el día indicado
    - **semanal**: Desde el lunes de la semana hasta la fecha indicada
    - **quincenal**: Desde el día 1 o 16 del mes (según la fecha) hasta la fecha indicada
    - **mensual**: Desde el día 1 del mes hasta la fecha indicada
    """
    return service.obtener_cierre(periodo, fecha)
