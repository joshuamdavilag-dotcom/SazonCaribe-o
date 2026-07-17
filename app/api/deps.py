from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decodificar_access_token
from app.models.personal import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.personal import RolEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Extrae y valida el usuario actual desde el token JWT.

    Decodifica el token, obtiene el ID del campo 'sub'
    y busca al usuario en la base de datos.

    Args:
        token: Token Bearer del header Authorization.
        db: Sesión de base de datos.

    Returns:
        Objeto Usuario autenticado.

    Raises:
        HTTPException 401: Token inválido o expirado.
        HTTPException 404: Usuario no encontrado en BD.
    """
    payload = decodificar_access_token(token)
    usuario_id = payload.get("sub")

    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    usuario_repo = UsuarioRepository(db)
    usuario = usuario_repo.get_by_id(int(usuario_id))

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    return usuario


def requerir_rol(roles_permitidos: List[RolEnum]):
    """
    Fábrica de dependencias que valida el rol del usuario autenticado.

    Crea una función dependiente que verifica si el rol del usuario
    está dentro de la lista de roles permitidos para el endpoint.

    Uso en endpoints:
        @router.get("/admin-only", dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR]))])

    Args:
        roles_permitidos: Lista de roles que tienen acceso al recurso.

    Returns:
        Función dependiente que valida el rol.
    """
    def _verificar_rol(current_user: Usuario = Depends(get_current_user)):
        try:
            rol_usuario = RolEnum(current_user.rol)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción"
            )

        if rol_usuario not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción"
            )

        return current_user

    return _verificar_rol
