from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verificar_password, crear_access_token
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth import LoginRequest, TokenResponse

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
    usuario = usuario_repo.get_by_username(data.username)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verificar_password(data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol
    }
    token = crear_access_token(data=payload)

    return TokenResponse(access_token=token)
