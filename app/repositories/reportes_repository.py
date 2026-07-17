from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict

from sqlalchemy import select, func, case, and_, literal_column
from sqlalchemy.orm import Session

from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.nomina import Nomina
from app.models.menu import MenuItem, Receta
from app.models.inventario import Insumo
from app.models.gasto import Gasto


class ReportesRepository:
    """
    Repositorio para consultas analíticas y financieras de cierre de caja.

    Ejecuta consultas SQL optimizadas para obtener métricas agrupadas
    por periodos de tiempo.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_ingresos_totales(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """
        Suma de todos los `Orden.total` con estado PAGADA
        dentro del rango de fechas.
        """
        stmt = select(
            func.coalesce(func.sum(Orden.total), Decimal("0.00"))
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                func.date(Orden.fecha_creacion) >= fecha_inicio,
                func.date(Orden.fecha_creacion) <= fecha_fin,
            )
        )
        return self.db.execute(stmt).scalar_one()

    def contar_ordenes(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Dict[str, int]:
        """Retorna conteo de órdenes pagadas y canceladas en el rango."""
        stmt = select(
            func.sum(case((Orden.estado == EstadoOrden.PAGADA, 1), else_=0)).label("pagadas"),
            func.sum(case((Orden.estado == EstadoOrden.CANCELADA, 1), else_=0)).label("canceladas"),
        ).where(
            and_(
                func.date(Orden.fecha_creacion) >= fecha_inicio,
                func.date(Orden.fecha_creacion) <= fecha_fin,
            )
        )
        row = self.db.execute(stmt).one()
        return {
            "pagadas": int(row.pagadas or 0),
            "canceladas": int(row.canceladas or 0),
        }

    def obtener_gastos_nomina(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """
        Suma de `Nomina.pago_neto` para nóminas con estado PAGADO
        cuyo `fecha_pago` caiga dentro del rango.
        """
        stmt = select(
            func.coalesce(func.sum(Nomina.pago_neto), Decimal("0.00"))
        ).where(
            and_(
                Nomina.estado == "PAGADO",
                Nomina.fecha_pago.isnot(None),
                func.date(Nomina.fecha_pago) >= fecha_inicio,
                func.date(Nomina.fecha_pago) <= fecha_fin,
            )
        )
        return self.db.execute(stmt).scalar_one()

    def obtener_costo_insumos(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """
        Calcula el costo total de ingredientes utilizados en las recetas
        vendidas durante el periodo.

        Lógica:
        1. Filtra DetalleOrden de órdenes PAGADA en el rango de fechas.
        2. Para cada detalle, navega: DetalleOrden -> Receta -> Insumo.
        3. Costo por detalle = SUM(cantidad_necesaria * insumo.costo_unitario) * cantidad_vendida
        4. Suma el total de todos los detalles.
        """
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        Receta.cantidad_necesaria
                        * Insumo.costo_unitario
                        * DetalleOrden.cantidad
                    ),
                    Decimal("0.00"),
                )
            )
            .select_from(Orden)
            .join(DetalleOrden, DetalleOrden.orden_id == Orden.id)
            .join(Receta, Receta.menu_item_id == DetalleOrden.producto_id)
            .join(Insumo, Insumo.id == Receta.insumo_id)
            .where(
                and_(
                    Orden.estado == EstadoOrden.PAGADA,
                    func.date(Orden.fecha_creacion) >= fecha_inicio,
                    func.date(Orden.fecha_creacion) <= fecha_fin,
                )
            )
        )
        return self.db.execute(stmt).scalar_one()

    def obtener_top_platillos(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        limite: int = 5,
    ) -> List[Dict]:
        """
        Retorna los N platillos más vendidos (por cantidad) en el rango.
        Solo considera órdenes PAGADA.
        """
        stmt = select(
            DetalleOrden.producto_id,
            MenuItem.nombre,
            func.sum(DetalleOrden.cantidad).label("cantidad_vendida"),
            func.sum(
                DetalleOrden.precio_unitario * DetalleOrden.cantidad
            ).label("ingresos_generados"),
        ).join(
            Orden, Orden.id == DetalleOrden.orden_id
        ).join(
            MenuItem, MenuItem.id == DetalleOrden.producto_id
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                func.date(Orden.fecha_creacion) >= fecha_inicio,
                func.date(Orden.fecha_creacion) <= fecha_fin,
            )
        ).group_by(
            DetalleOrden.producto_id,
            MenuItem.nombre,
        ).order_by(
            func.sum(DetalleOrden.cantidad).desc()
        ).limit(limite)

        rows = self.db.execute(stmt).all()
        return [
            {
                "producto_id": row.producto_id,
                "nombre": row.nombre,
                "cantidad_vendida": int(row.cantidad_vendida),
                "ingresos_generados": float(row.ingresos_generados),
            }
            for row in rows
        ]

    def obtener_gastos_operativos(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        stmt = select(
            func.coalesce(func.sum(Gasto.monto), Decimal("0.00"))
        ).where(
            and_(
                func.date(Gasto.fecha) >= fecha_inicio,
                func.date(Gasto.fecha) <= fecha_fin,
            )
        )
        return self.db.execute(stmt).scalar_one()
