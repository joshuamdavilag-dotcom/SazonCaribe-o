from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asistencia import Asistencia, Turno
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
            nombre: Nombre del turno (ej. "Matutino", "Nocturno").

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

    def tiene_asistencias(self, turno_id: int) -> bool:
        """Indica si el turno ya tiene asistencias registradas.

        Usa un COUNT en lugar de cargar la colección completa, que crece sin
        límite con el paso del tiempo.

        Args:
            turno_id: ID del turno a verificar.

        Returns:
            True si existe al menos una asistencia asociada.
        """
        statement = select(func.count(Asistencia.id)).where(
            Asistencia.turno_id == turno_id
        )
        return bool(self.db.execute(statement).scalar_one())
