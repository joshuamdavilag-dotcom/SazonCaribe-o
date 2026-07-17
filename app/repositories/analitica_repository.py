from datetime import date
from typing import Optional, Dict

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.menu import MenuItem


class AnaliticaRepository:
    """
    Repositorio para el módulo de Analítica y Reportes Financieros.
    
    Ejecuta agregaciones SQL optimizadas sobre las tablas de órdenes
    para extraer métricas de cierre de caja y productos estrella.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_metricas_caja(self, fecha_consulta: date) -> Dict:
        """
        Calcula las métricas de cierre de caja para una fecha específica.

        Ejecuta COUNT y SUM sobre la tabla ordenes filtrando por fecha,
        separando el conteo de pagadas vs canceladas.

        Args:
            fecha_consulta: Fecha para la que se calculan las métricas.

        Returns:
            Dict con total_ventas, pagadas_count, canceladas_count.
        """
        stmt_total = (
            select(func.coalesce(func.sum(Orden.total), 0.0))
            .where(Orden.estado == EstadoOrden.PAGADA)
            .where(func.date(Orden.fecha_creacion) == fecha_consulta)
        )
        total_ventas = self.db.execute(stmt_total).scalar()

        stmt_pagadas = (
            select(func.count(Orden.id))
            .where(Orden.estado == EstadoOrden.PAGADA)
            .where(func.date(Orden.fecha_creacion) == fecha_consulta)
        )
        pagadas_count = self.db.execute(stmt_pagadas).scalar()

        stmt_canceladas = (
            select(func.count(Orden.id))
            .where(Orden.estado == EstadoOrden.CANCELADA)
            .where(func.date(Orden.fecha_creacion) == fecha_consulta)
        )
        canceladas_count = self.db.execute(stmt_canceladas).scalar()

        return {
            "total_ventas": float(total_ventas),
            "pagadas_count": pagadas_count,
            "canceladas_count": canceladas_count
        }

    def obtener_producto_estrella(self, fecha_consulta: date) -> Optional[Dict]:
        """
        Encuentra el producto más vendido en órdenes pagadas de una fecha.

        Realiza un JOIN entre DetalleOrden → Orden → MenuItem,
        agrupa por producto y ordena por cantidad total vendida descendente.

        Args:
            fecha_consulta: Fecha para buscar el producto estrella.

        Returns:
            Dict con producto_id, nombre, cantidad_vendida o None.
        """
        stmt = (
            select(
                DetalleOrden.producto_id,
                MenuItem.nombre,
                func.sum(DetalleOrden.cantidad).label("cantidad_vendida")
            )
            .join(Orden, DetalleOrden.orden_id == Orden.id)
            .join(MenuItem, DetalleOrden.producto_id == MenuItem.id)
            .where(Orden.estado == EstadoOrden.PAGADA)
            .where(func.date(Orden.fecha_creacion) == fecha_consulta)
            .group_by(DetalleOrden.producto_id, MenuItem.nombre)
            .order_by(desc("cantidad_vendida"))
            .limit(1)
        )

        result = self.db.execute(stmt).first()

        if not result:
            return None

        return {
            "producto_id": result[0],
            "nombre": result[1],
            "cantidad_vendida": int(result[2])
        }
