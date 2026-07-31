from datetime import date, timedelta

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

    Para el periodo DIARIO (caja actual) utiliza el estado abierto
    basado en `cierre_caja_id IS NULL`.
    Para periodos analíticos (SEMANAL, QUINCENAL, MENSUAL) usa
    filtros por rango de fechas.
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

        - diario:    (None, None) → señal para usar cierre_caja_id IS NULL
        - semanal:   lunes de esta semana → hoy
        - quincenal: día 1 del mes → hoy (si hoy <= 15)
                   o día 16 del mes → hoy (si hoy > 15)
        - mensual:   día 1 del mes → hoy
        """
        if periodo == PeriodoEnum.DIARIO:
            return None, None

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

        if fecha_inicio is None:
            ingresos = self.repo.obtener_ingresos_totales_sin_archivar()
            conteo = self.repo.contar_ordenes_sin_archivar()
            gastos_clasificados = self.repo.obtener_gastos_clasificados_sin_archivar()
            gastos_nomina = (
                self.repo.obtener_gastos_nomina(hoy, hoy)
                + gastos_clasificados["gastos_nomina"]
            )
            costos = (
                self.repo.obtener_costo_insumos_sin_archivar()
                + gastos_clasificados["costo_insumos"]
            )
            gastos_operativos = gastos_clasificados["gastos_operativos"]
            descuentos = self.repo.obtener_descuentos_totales_sin_archivar()
            top_platillos = self.repo.obtener_top_platillos_sin_archivar()
            fecha_inicio = hoy
            fecha_fin = hoy
        else:
            ingresos = self.repo.obtener_ingresos_totales(fecha_inicio, fecha_fin)
            conteo = self.repo.contar_ordenes(fecha_inicio, fecha_fin)
            gastos_clasificados = self.repo.obtener_gastos_clasificados(fecha_inicio, fecha_fin)
            gastos_nomina = (
                self.repo.obtener_gastos_nomina(fecha_inicio, fecha_fin)
                + gastos_clasificados["gastos_nomina"]
            )
            costos = (
                self.repo.obtener_costo_insumos(fecha_inicio, fecha_fin)
                + gastos_clasificados["costo_insumos"]
            )
            gastos_operativos = gastos_clasificados["gastos_operativos"]
            descuentos = self.repo.obtener_descuentos_totales(fecha_inicio, fecha_fin)
            top_platillos = self.repo.obtener_top_platillos(fecha_inicio, fecha_fin)

        ingresos_f = float(ingresos)
        gastos_nomina_f = float(gastos_nomina)
        costos_f = float(costos)
        gastos_operativos_f = float(gastos_operativos)
        descuentos_f = float(descuentos)
        ingresos_brutos = ingresos_f + descuentos_f

        return CierreCajaPeriodoResponse(
            periodo=periodo.value,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            ingresos_totales=ingresos_f,
            total_descuentos=descuentos_f,
            ingresos_brutos=ingresos_brutos,
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
