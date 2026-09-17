import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verificar_password, crear_access_token
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.personal import RolEnum

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description="Autentica un usuario y retorna un token JWT de acceso."
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Endpoint de autenticación.

    - Valida que el usuario exista.
    - Verifica la contraseña contra el hash bcrypt.
    - Retorna un token JWT con id, username y rol.
    """
    usuario_repo = UsuarioRepository(db)
    username_norm = data.username.strip().lower()
    usuario = usuario_repo.get_by_username(username_norm)

    logger.info(
        "Login intent username=%r usuario_existe=%s",
        username_norm,
        usuario is not None,
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    password_valida = verificar_password(data.password, usuario.password_hash)
    logger.info(
        "Login intent username=%r password_valida=%s",
        username_norm,
        password_valida,
    )

    if not password_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if usuario.rol == RolEnum.VENDEDOR.value and not usuario.turno_habilitado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu turno de trabajo no está habilitado actualmente por gerencia."
        )

    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol
    }
    token = crear_access_token(data=payload)

    return TokenResponse(access_token=token)
