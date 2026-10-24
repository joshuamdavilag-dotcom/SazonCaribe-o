from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.orden import Orden, EstadoOrden
from app.models.gasto import Gasto
from app.models.caja import CierreCaja


class CajaRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_ordenes_pagadas_sin_archivar(self) -> List[Orden]:
        statement = (
            select(Orden)
            .options(joinedload(Orden.detalles))
            .where(
                Orden.estado == EstadoOrden.PAGADA,
                Orden.cierre_caja_id.is_(None),
            )
            .order_by(Orden.fecha_creacion.desc())
        )
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def obtener_gastos_sin_archivar(self) -> List[Gasto]:
        statement = (
            select(Gasto)
            .where(Gasto.cierre_caja_id.is_(None))
            .order_by(Gasto.fecha.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def calcular_totales(
        self,
        ordenes: List[Orden],
    ) -> dict:
        total_ventas = sum(Decimal(str(o.total)) for o in ordenes)
        return {
            "total_ventas": float(total_ventas),
            "total_ordenes": len(ordenes),
        }

    def crear_cierre(
        self,
        total_ventas: float,
        total_ordenes: int,
        cerrado_por: Optional[int],
    ) -> CierreCaja:
        cierre = CierreCaja(
            total_ventas=total_ventas,
            total_ordenes=total_ordenes,
            cerrado_por=cerrado_por,
        )
        self.db.add(cierre)
        self.db.flush()
        return cierre

    def archivar_ordenes(
        self,
        ordenes: List[Orden],
        cierre: CierreCaja,
    ) -> None:
        for orden in ordenes:
            orden.cierre_caja_id = cierre.id
        self.db.flush()

    def archivar_gastos(
        self,
        gastos: List[Gasto],
        cierre: CierreCaja,
    ) -> None:
        for gasto in gastos:
            gasto.cierre_caja_id = cierre.id
        self.db.flush()
