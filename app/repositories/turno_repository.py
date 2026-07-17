from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asistencia import Turno
from app.repositories.base_repository import BaseRepository


class TurnoRepository(BaseRepository[Turno]):
    """
    Repositorio para el modelo Turno.

    Extiende BaseRepository con métodos específicos
    para la gestión de turnos laborales.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Turno, db)

    def get_by_nombre(self, nombre: str) -> Optional[Turno]:
        """
        Busca un turno por su nombre.

        Args:
            nombre: Nombre del turno (ej. "Mañana", "Tarde", "Noche").

        Returns:
            El turno encontrado o None si no existe.
        """
        statement = select(Turno).where(Turno.nombre == nombre)
        return self.db.execute(statement).scalar_one_or_none()

    def exists_by_nombre(self, nombre: str) -> bool:
        """
        Verifica si existe un turno con el nombre dado.

        Args:
            nombre: Nombre del turno a verificar.

        Returns:
            True si existe, False si no.
        """
        return self.get_by_nombre(nombre) is not None
