from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.orden import Orden, EstadoOrden
from app.models.gasto import Gasto
from app.models.caja import CierreCaja


class CajaRepository:
    """Acceso a datos de la sesión de caja abierta (órdenes y gastos sin archivar)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_ordenes_pagadas_sin_archivar(self) -> List[Orden]:
        """Devuelve las órdenes PAGADA de la caja abierta actual, con sus detalles cargados."""
        statement = (
            select(Orden)
            .options(joinedload(Orden.detalles))
            .where(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.cierre_caja_id.is_(None),
                Orden.anulada.is_(False),
            )
            .order_by(Orden.fecha_creacion.desc())
        )
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def obtener_gastos_sin_archivar(self) -> List[Gasto]:
        """Devuelve los gastos que aún no han sido archivados en un cierre de caja."""
        statement = (
            select(Gasto)
            .where(
                Gasto.cierre_caja_id.is_(None),
                Gasto.eliminado.is_(False),
            )
            .order_by(Gasto.fecha.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def calcular_totales(
        self,
        ordenes: List[Orden],
    ) -> dict:
        """Suma ventas y descuentos del conjunto de órdenes recibido."""
        total_ventas = sum(Decimal(str(o.total)) for o in ordenes)
        total_descuentos = sum(Decimal(str(o.descuento_total or 0)) for o in ordenes)
        return {
            "total_ventas": float(total_ventas),
            "total_ordenes": len(ordenes),
            "total_descuentos": float(total_descuentos),
        }

    def crear_cierre(
        self,
        total_ventas: float,
        total_ordenes: int,
        cerrado_por: Optional[int],
        fecha_cierre: Optional[datetime] = None,
    ) -> CierreCaja:
        """Inserta un registro de cierre de caja y devuelve la entidad con su id asignado.

        Args:
            fecha_cierre: Hora local exacta del cierre. Si es None se deja el
                valor por defecto de la columna (usado por el cierre manual).
        """
        datos = {
            "total_ventas": total_ventas,
            "total_ordenes": total_ordenes,
            "cerrado_por": cerrado_por,
        }
        if fecha_cierre is not None:
            datos["fecha_cierre"] = fecha_cierre
        cierre = CierreCaja(**datos)
        self.db.add(cierre)
        self.db.flush()
        return cierre

    def archivar_ordenes(
        self,
        ordenes: List[Orden],
        cierre: CierreCaja,
    ) -> None:
        """Vincula cada orden al cierre de caja, sacándolas de la caja abierta."""
        for orden in ordenes:
            orden.cierre_caja_id = cierre.id
        self.db.flush()

    def archivar_gastos(
        self,
        gastos: List[Gasto],
        cierre: CierreCaja,
    ) -> None:
        """Vincula cada gasto al cierre de caja, sacándolos de la caja abierta."""
        for gasto in gastos:
            gasto.cierre_caja_id = cierre.id
        self.db.flush()
