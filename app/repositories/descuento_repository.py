from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.descuento import DescuentoFrecuente
from app.repositories.base_repository import BaseRepository


class DescuentoFrecuenteRepository(BaseRepository[DescuentoFrecuente]):
    """Acceso a datos de los descuentos frecuentes guardados por el negocio."""

    def __init__(self, db: Session) -> None:
        super().__init__(DescuentoFrecuente, db)

    def listar(self, solo_activos: bool = False) -> List[DescuentoFrecuente]:
        """Devuelve los descuentos ordenados por nombre; opcionalmente solo los activos."""
        stmt = select(DescuentoFrecuente)
        if solo_activos:
            stmt = stmt.where(DescuentoFrecuente.activo.is_(True))
        stmt = stmt.order_by(DescuentoFrecuente.nombre.asc())
        return list(self.db.execute(stmt).scalars().all())

    def obtener_por_nombre(self, nombre: str) -> Optional[DescuentoFrecuente]:
        """Busca un descuento por su nombre exacto (ignora espacios extremos)."""
        stmt = select(DescuentoFrecuente).where(
            DescuentoFrecuente.nombre == nombre.strip()
        )
        return self.db.execute(stmt).scalars().first()
