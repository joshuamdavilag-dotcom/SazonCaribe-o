import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permisos import permisos_efectivos
from app.core.security import verificar_password, crear_access_token
from app.models.personal import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth import LoginRequest, TokenResponse, AuthMeResponse
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
    try:
        usuario = usuario_repo.get_by_username(username_norm)
    except Exception as e:
        logger.error("Error de base de datos en login: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No hay conexión con la base de datos. "
                "Verifica la variable DATABASE_URL en Render "
                "(usa la Internal Database URL de PostgreSQL)."
            ),
        )

    logger.info(
        "Login intent username=%r usuario_existe=%s",
        username_norm,
        usuario is not None,
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No existe el usuario '{username_norm}'",
            headers={"WWW-Authenticate": "Bearer"}
        )

    password_valida = verificar_password(data.password, usuario.password_hash)
    logger.info(
        "Login intent username=%r password_valida=%s hash_prefix=%r",
        username_norm,
        password_valida,
        (usuario.password_hash or "")[:7],
    )

    if not password_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu usuario está desactivado. Contacta a gerencia."
        )

    if usuario.rol == RolEnum.VENDEDOR.value and not usuario.turno_habilitado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu turno de trabajo no está habilitado actualmente por gerencia."
        )

    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol,
        "puesto": usuario.empleado.puesto.nombre if usuario.empleado and usuario.empleado.puesto else None,
        "permisos": permisos_efectivos(usuario),
    }
    token = crear_access_token(data=payload)

    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Obtener sesión actual",
    description=(
        "Valida la sesión actual. Devuelve los datos del usuario autenticado. "
        "Rechaza con 403 'TURNO_DESHABILITADO' si un Vendedor tiene su turno "
        "deshabilitado por gerencia, o con 403 'USUARIO_DESACTIVADO' si el "
        "usuario fue desactivado. Lo usa el frontend para invalidar sesiones "
        "activas vía polling."
    ),
)
def obtener_usuario_actual(
    current_user: Usuario = Depends(get_current_user)
) -> AuthMeResponse:
    """
    Retorna el usuario autenticado junto con el estado de su turno.

    - **turno_habilitado**: false en Vendedor → 403 TURNO_DESHABILITADO.
    - **activo**: false → 403 USUARIO_DESACTIVADO.
    """
    return AuthMeResponse(
        id=current_user.id,
        username=current_user.username,
        rol=current_user.rol,
        puesto=current_user.empleado.puesto.nombre if current_user.empleado and current_user.empleado.puesto else None,
        turno_habilitado=current_user.turno_habilitado,
        activo=current_user.activo,
        permisos=permisos_efectivos(current_user),
    )
