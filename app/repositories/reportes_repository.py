from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional, List, Dict

from sqlalchemy import select, func, case, and_, literal_column
from sqlalchemy.orm import Session

from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.nomina import Nomina, AdelantoSalario
from app.models.menu import MenuItem
from app.models.gasto import Gasto, CategoriaGasto


def _rango_datetime(
    fecha_inicio: date, fecha_fin: date
) -> tuple[datetime, datetime]:
    """Convierte un rango de fechas inclusivo en un rango datetime semiabierto.

    Se usa ``[inicio 00:00, fin+1 00:00)`` para que MySQL pueda aprovechar el
    índice de la columna. ``func.date(columna)`` obliga a recorrer la tabla
    completa porque aplica una función sobre la columna indexada.
    """
    return (
        datetime.combine(fecha_inicio, time.min),
        datetime.combine(fecha_fin + timedelta(days=1), time.min),
    )


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
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = select(
            func.coalesce(func.sum(Orden.total), Decimal("0.00"))
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.anulada.is_(False),
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
            )
        )
        return self.db.execute(stmt).scalar_one()

    def contar_ordenes(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Dict[str, int]:
        """Retorna conteo de órdenes pagadas y canceladas en el rango."""
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = select(
            func.sum(case((and_(Orden.estado == EstadoOrden.PAGADA, Orden.anulada.is_(False)), 1), else_=0)).label("pagadas"),
            func.sum(case((Orden.estado == EstadoOrden.CANCELADA, 1), else_=0)).label("canceladas"),
        ).where(
            and_(
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
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
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = select(
            func.coalesce(func.sum(Nomina.pago_neto), Decimal("0.00"))
        ).where(
            and_(
                Nomina.estado == "PAGADO",
                Nomina.fecha_pago.isnot(None),
                Nomina.fecha_pago >= inicio,
                Nomina.fecha_pago < fin,
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
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
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
                Orden.anulada.is_(False),
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
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

    def obtener_descuentos_totales(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """Suma de todos los descuentos aplicados en órdenes PAGADA del periodo."""
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = select(
            func.coalesce(func.sum(Orden.descuento_total), Decimal("0.00"))
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.anulada.is_(False),
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
            )
        )
        return self.db.execute(stmt).scalar_one()

    def _stmt_resumen_ordenes(self):
        """Columnas agregadas de órdenes en UNA sola consulta (1 viaje a la BD).

        Reúne ingresos, descuentos y conteos de pagadas/canceladas, que antes
        se pedían en tres consultas separadas a MySQL remoto.
        """
        pagada = and_(Orden.estado == EstadoOrden.PAGADA, Orden.anulada.is_(False))
        return select(
            func.coalesce(
                func.sum(case((pagada, Orden.total), else_=0)), Decimal("0.00")
            ).label("ingresos"),
            func.coalesce(
                func.sum(case((pagada, Orden.descuento_total), else_=0)),
                Decimal("0.00"),
            ).label("descuentos"),
            func.coalesce(
                func.sum(case((pagada, 1), else_=0)), 0
            ).label("pagadas"),
            func.coalesce(
                func.sum(case((Orden.estado == EstadoOrden.CANCELADA, 1), else_=0)),
                0,
            ).label("canceladas"),
        )

    @staticmethod
    def _resumen_a_dict(row) -> Dict:
        return {
            "ingresos": row.ingresos,
            "descuentos": row.descuentos,
            "pagadas": int(row.pagadas or 0),
            "canceladas": int(row.canceladas or 0),
        }

    def obtener_resumen_ordenes(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Dict:
        """Ingresos, descuentos y conteos de órdenes del rango en una consulta."""
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = self._stmt_resumen_ordenes().where(
            Orden.fecha_creacion >= inicio,
            Orden.fecha_creacion < fin,
        )
        return self._resumen_a_dict(self.db.execute(stmt).one())

    def obtener_resumen_ordenes_sin_archivar(self) -> Dict:
        """Ingresos, descuentos y conteos de la caja abierta en una consulta."""
        stmt = self._stmt_resumen_ordenes().where(Orden.cierre_caja_id.is_(None))
        return self._resumen_a_dict(self.db.execute(stmt).one())

    def _stmt_gastos_clasificados(self, *filtros):
        """Consulta que clasifica los gastos de la tabla `gastos` en 3 buckets.

        - costo_insumos:    categoría SUMINISTROS (consumo de inventario)
        - gastos_nomina:    adelantos de salario (gastos ligados a adelantos_salario)
        - gastos_operativos: el resto (OPERATIVO, MANTENIMIENTO, SERVICIOS,
                            IMPUESTOS, OTROS)
        """
        adelanto_subq = select(AdelantoSalario.gasto_id).where(
            AdelantoSalario.gasto_id.isnot(None)
        ).scalar_subquery()
        stmt = select(
            func.coalesce(
                func.sum(case(
                    (Gasto.categoria == CategoriaGasto.SUMINISTROS, Gasto.monto),
                    else_=0,
                )),
                Decimal("0.00"),
            ).label("costo_insumos"),
            func.coalesce(
                func.sum(case(
                    (Gasto.id.in_(adelanto_subq), Gasto.monto),
                    else_=0,
                )),
                Decimal("0.00"),
            ).label("gastos_nomina"),
            func.coalesce(
                func.sum(case(
                    (
                        and_(
                            Gasto.categoria != CategoriaGasto.SUMINISTROS,
                            Gasto.id.notin_(adelanto_subq),
                        ),
                        Gasto.monto,
                    ),
                    else_=0,
                )),
                Decimal("0.00"),
            ).label("gastos_operativos"),
        ).where(Gasto.eliminado.is_(False))
        if filtros:
            stmt = stmt.where(*filtros)
        return stmt

    def obtener_gastos_clasificados(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Dict[str, Decimal]:
        """Clasifica los gastos de la tabla `gastos` dentro del rango de fechas."""
        inicio, fin = _rango_datetime(fecha_inicio, fecha_fin)
        stmt = self._stmt_gastos_clasificados(
            Gasto.fecha >= inicio,
            Gasto.fecha < fin,
        )
        row = self.db.execute(stmt).one()
        return {
            "costo_insumos": row.costo_insumos,
            "gastos_nomina": row.gastos_nomina,
            "gastos_operativos": row.gastos_operativos,
        }

    # ─── Métodos para caja actual (sin archivar) ───────────────────────

    def obtener_ingresos_totales_sin_archivar(self) -> Decimal:
        """Suma de los totales de órdenes PAGADA aún no archivadas (caja actual)."""
        stmt = select(
            func.coalesce(func.sum(Orden.total), Decimal("0.00"))
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.cierre_caja_id.is_(None),
                Orden.anulada.is_(False),
            )
        )
        return self.db.execute(stmt).scalar_one()

    def contar_ordenes_sin_archivar(self) -> Dict[str, int]:
        """Retorna el conteo de órdenes pagadas y canceladas aún no archivadas."""
        pagadas = select(func.count(Orden.id)).where(
            Orden.estado == EstadoOrden.PAGADA,
            Orden.cierre_caja_id.is_(None),
            Orden.anulada.is_(False),
        )
        canceladas = select(func.count(Orden.id)).where(
            Orden.estado == EstadoOrden.CANCELADA,
            Orden.cierre_caja_id.is_(None),
        )
        return {
            "pagadas": self.db.execute(pagadas).scalar_one() or 0,
            "canceladas": self.db.execute(canceladas).scalar_one() or 0,
        }

    def obtener_descuentos_totales_sin_archivar(self) -> Decimal:
        """Suma de los descuentos de órdenes PAGADA aún no archivadas."""
        stmt = select(
            func.coalesce(func.sum(Orden.descuento_total), Decimal("0.00"))
        ).where(
            and_(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.cierre_caja_id.is_(None),
                Orden.anulada.is_(False),
            )
        )
        return self.db.execute(stmt).scalar_one()

    def obtener_top_platillos_sin_archivar(
        self,
        limite: int = 5,
    ) -> List[Dict]:
        """
        Retorna los N platillos más vendidos en órdenes PAGADA no archivadas.

        Args:
            limite: Cantidad máxima de platillos a devolver.

        Returns:
            Lista de platillos con su nombre, cantidad vendida e ingresos generados.
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
                Orden.cierre_caja_id.is_(None),
                Orden.anulada.is_(False),
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

    def obtener_gastos_clasificados_sin_archivar(self) -> Dict[str, Decimal]:
        """Clasifica los gastos sin archivar (caja actual, cierre_caja_id IS NULL)."""
        stmt = self._stmt_gastos_clasificados(Gasto.cierre_caja_id.is_(None))
        row = self.db.execute(stmt).one()
        return {
            "costo_insumos": row.costo_insumos,
            "gastos_nomina": row.gastos_nomina,
            "gastos_operativos": row.gastos_operativos,
        }
