from datetime import date
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nomina import Nomina
from app.repositories.base_repository import BaseRepository


class NominaRepository(BaseRepository[Nomina]):
    """
    Repositorio para el modelo Nomina.

    Extiende BaseRepository con métodos específicos
    para la gestión de nóminas quincenales.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Nomina, db)

    def get_by_periodo_y_empleado(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date
    ) -> Optional[Nomina]:
        """
        Busca un registro de nómina para un empleado en un período específico.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del período.
            fecha_fin: Fecha de fin del período.

        Returns:
            El registro de nómina encontrado o None si no existe.
        """
        statement = select(Nomina).where(
            Nomina.empleado_id == empleado_id,
            Nomina.fecha_inicio == fecha_inicio,
            Nomina.fecha_fin == fecha_fin
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_empleado(self, empleado_id: int) -> List[Nomina]:
        """
        Obtiene todo el historial de nóminas de un empleado.

        Args:
            empleado_id: ID del empleado.

        Returns:
            Lista de nóminas ordenadas por fecha descendente.
        """
        statement = (
            select(Nomina)
            .where(Nomina.empleado_id == empleado_id)
            .order_by(Nomina.fecha_inicio.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_by_estado(self, estado: str) -> List[Nomina]:
        """
        Obtiene todas las nóminas con un estado específico.

        Args:
            estado: Estado a filtrar ("PENDIENTE" o "PAGADO").

        Returns:
            Lista de nóminas con el estado especificado.
        """
        statement = (
            select(Nomina)
            .where(Nomina.estado == estado)
            .order_by(Nomina.fecha_inicio.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_pendientes(self) -> List[Nomina]:
        """
        Obtiene todas las nóminas pendientes de pago.

        Returns:
            Lista de nóminas con estado "PENDIENTE".
        """
        return self.get_by_estado("PENDIENTE")

    def get_pagadas(self) -> List[Nomina]:
        """
        Obtiene todas las nóminas ya pagadas.

        Returns:
            Lista de nóminas con estado "PAGADO".
        """
        return self.get_by_estado("PAGADO")

    def exists_by_periodo_y_empleado(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date
    ) -> bool:
        """
        Verifica si ya existe un registro de nómina para el empleado en el período.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del período.
            fecha_fin: Fecha de fin del período.

        Returns:
            True si existe, False si no.
        """
        return self.get_by_periodo_y_empleado(
            empleado_id, fecha_inicio, fecha_fin
        ) is not None
