from datetime import date

from sqlalchemy.orm import Session

from app.repositories.analitica_repository import AnaliticaRepository
from app.schemas.analitica import CierreCajaResponse, ProductoEstrellaResponse


class AnaliticaService:
    """
    Servicio de lógica de negocio para el módulo de Analítica.

    Coordina las consultas de métricas financieras
    y las retorna como esquemas listos para la API.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AnaliticaRepository(db)

    def obtener_cierre_caja(
        self,
        fecha_consulta: date
    ) -> CierreCajaResponse:
        """
        Genera el reporte de cierre de caja para una fecha.

        Args:
            fecha_consulta: Fecha para el cierre de caja.

        Returns:
            CierreCajaResponse con las métricas y el producto estrella.
        """
        metricas = self.repo.obtener_metricas_caja(fecha_consulta)
        producto = self.repo.obtener_producto_estrella(fecha_consulta)

        producto_estrella = None
        if producto:
            producto_estrella = ProductoEstrellaResponse(**producto)

        return CierreCajaResponse(
            fecha=fecha_consulta,
            total_ventas=metricas["total_ventas"],
            ordenes_pagadas_count=metricas["pagadas_count"],
            ordenes_canceladas_count=metricas["canceladas_count"],
            producto_estrella=producto_estrella
        )
