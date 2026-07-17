from datetime import date, timedelta
from calendar import monthrange

from sqlalchemy.orm import Session

from app.repositories.reportes_repository import ReportesRepository
from app.schemas.reportes import (
    PeriodoEnum,
    CierreCajaPeriodoResponse,
    TopPlatilloResponse,
)


class ReportesService:
    """
    Servicio de lógica de negocio para reportes de cierre de caja.

    Calcula rangos de fechas según el periodo solicitado y coordina
    las consultas del repositorio para producir métricas financieras.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReportesRepository(db)

    # =========================================================================
    # Cálculo de rangos de fecha
    # =========================================================================

    @staticmethod
    def _calcular_rango(periodo: PeriodoEnum, hoy: date) -> tuple[date, date]:
        """
        Calcula (fecha_inicio, fecha_fin) según el periodo y la fecha actual.

        - diario:    hoy → hoy
        - semanal:   lunes de esta semana → hoy
        - quincenal: día 1 del mes → hoy (si hoy <= 15)
                   o día 16 del mes → hoy (si hoy > 15)
        - mensual:   día 1 del mes → hoy
        """
        if periodo == PeriodoEnum.DIARIO:
            return hoy, hoy

        if periodo == PeriodoEnum.SEMANAL:
            lunes = hoy - timedelta(days=hoy.weekday())
            return lunes, hoy

        if periodo == PeriodoEnum.QUINCENAL:
            if hoy.day <= 15:
                inicio = date(hoy.year, hoy.month, 1)
            else:
                inicio = date(hoy.year, hoy.month, 16)
            return inicio, hoy

        if periodo == PeriodoEnum.MENSUAL:
            inicio = date(hoy.year, hoy.month, 1)
            return inicio, hoy

        return hoy, hoy

    # =========================================================================
    # Endpoint principal
    # =========================================================================

    def obtener_cierre(
        self,
        periodo: PeriodoEnum,
        fecha_consulta: date | None = None,
    ) -> CierreCajaPeriodoResponse:
        """
        Genera el reporte de cierre de caja para el periodo y fecha dados.

        Args:
            periodo: Tipo de periodo (diario, semanal, quincenal, mensual).
            fecha_consulta: Fecha de referencia (default: hoy).

        Returns:
            CierreCajaPeriodoResponse con todas las métricas.
        """
        hoy = fecha_consulta or date.today()
        fecha_inicio, fecha_fin = self._calcular_rango(periodo, hoy)

        ingresos = self.repo.obtener_ingresos_totales(fecha_inicio, fecha_fin)
        conteo = self.repo.contar_ordenes(fecha_inicio, fecha_fin)
        gastos_nomina = self.repo.obtener_gastos_nomina(fecha_inicio, fecha_fin)
        costos = self.repo.obtener_costo_insumos(fecha_inicio, fecha_fin)
        gastos_operativos = self.repo.obtener_gastos_operativos(fecha_inicio, fecha_fin)
        top_platillos = self.repo.obtener_top_platillos(fecha_inicio, fecha_fin)

        ingresos_f = float(ingresos)
        gastos_nomina_f = float(gastos_nomina)
        costos_f = float(costos)
        gastos_operativos_f = float(gastos_operativos)

        return CierreCajaPeriodoResponse(
            periodo=periodo.value,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            ingresos_totales=ingresos_f,
            gastos_nomina=gastos_nomina_f,
            costo_insumos=costos_f,
            gastos_operativos=gastos_operativos_f,
            utilidad_neta=ingresos_f - (gastos_nomina_f + costos_f + gastos_operativos_f),
            ordenes_pagadas=conteo["pagadas"],
            ordenes_canceladas=conteo["canceladas"],
            top_platillos=[
                TopPlatilloResponse(**p) for p in top_platillos
            ],
        )
