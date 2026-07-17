from datetime import date
from decimal import Decimal
from typing import List

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.gasto import Gasto
from app.repositories.base_repository import BaseRepository


class GastoRepository(BaseRepository[Gasto]):

    def __init__(self, db: Session) -> None:
        super().__init__(Gasto, db)

    def obtener_por_rango(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> List[Gasto]:
        stmt = (
            select(Gasto)
            .where(
                and_(
                    func.date(Gasto.fecha) >= fecha_inicio,
                    func.date(Gasto.fecha) <= fecha_fin,
                )
            )
            .order_by(Gasto.fecha.desc())
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def sumar_por_rango(
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
