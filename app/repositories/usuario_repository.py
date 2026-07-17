from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personal import Usuario
from app.repositories.base_repository import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    """
    Repositorio para el modelo Usuario.

    Extiende BaseRepository con métodos específicos
    para la gestión de usuarios del sistema.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Usuario, db)

    def get_by_username(self, username: str) -> Optional[Usuario]:
        """
        Busca un usuario por su nombre de usuario (credencial).

        Args:
            username: Nombre de usuario a buscar.

        Returns:
            El usuario encontrado o None si no existe.
        """
        statement = select(Usuario).where(Usuario.username == username)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_empleado_id(self, empleado_id: int) -> Optional[Usuario]:
        """
        Busca un usuario por el ID del empleado asociado.

        Args:
            empleado_id: ID del empleado.

        Returns:
            El usuario encontrado o None si no existe.
        """
        statement = select(Usuario).where(
            Usuario.empleado_id == empleado_id
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_rol(self, rol: str) -> list[Usuario]:
        """
        Obtiene todos los usuarios con un rol específico.

        Args:
            rol: Rol a buscar (Administrador, Gerente, Vendedor).

        Returns:
            Lista de usuarios con el rol especificado.
        """
        statement = select(Usuario).where(Usuario.rol == rol)
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def exists_by_username(self, username: str) -> bool:
        """
        Verifica si existe un usuario con el username dado.

        Args:
            username: Nombre de usuario a verificar.

        Returns:
            True si existe, False si no.
        """
        statement = select(Usuario).where(Usuario.username == username)
        return self.db.execute(statement).scalar_one_or_none() is not None
