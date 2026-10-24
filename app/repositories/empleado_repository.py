from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personal import Empleado
from app.repositories.base_repository import BaseRepository


class EmpleadoRepository(BaseRepository[Empleado]):
    """
    Repositorio para el modelo Empleado.

    Extiende BaseRepository con métodos específicos
    para la gestión de empleados del restaurante.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Empleado, db)

    def get_by_cedula(self, cedula: str) -> Optional[Empleado]:
        """
        Busca un empleado por su cédula de identidad.

        Args:
            cedula: Número de cédula a buscar.

        Returns:
            El empleado encontrado o None si no existe.
        """
        statement = select(Empleado).where(
            Empleado.cedula_identidad == cedula
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_puesto(self, puesto_id: int) -> List[Empleado]:
        """
        Obtiene todos los empleados de un puesto específico.

        Args:
            puesto_id: ID del puesto.

        Returns:
            Lista de empleados en el puesto.
        """
        statement = select(Empleado).where(
            Empleado.puesto_id == puesto_id
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_activos(self) -> List[Empleado]:
        """
        Obtiene todos los empleados activos.

        Returns:
            Lista de empleados activos.
        """
        statement = select(Empleado).where(Empleado.activo == True)
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_inactivos(self) -> List[Empleado]:
        """
        Obtiene todos los empleados inactivos.

        Returns:
            Lista de empleados inactivos.
        """
        statement = select(Empleado).where(Empleado.activo == False)
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def exists_by_cedula(self, cedula: str) -> bool:
        """
        Verifica si existe un empleado con la cédula dada.

        Args:
            cedula: Número de cédula a verificar.

        Returns:
            True si existe, False si no.
        """
        statement = select(Empleado).where(
            Empleado.cedula_identidad == cedula
        )
        return self.db.execute(statement).scalar_one_or_none() is not None

    def desactivar(self, id: int) -> Optional[Empleado]:
        """
        Desactiva un empleado (baja lógica).

        Args:
            id: ID del empleado a desactivar.

        Returns:
            El empleado desactivado o None si no existe.
        """
        return self.update(id, {"activo": False})
