from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.core.config import get_settings


# =============================================================================
# Constantes de Seguridad JWT (leídas desde .env vía Pydantic Settings)
# =============================================================================

settings = get_settings()

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


# =============================================================================
# Funciones de Contraseña (bcrypt directo, sin passlib)
# =============================================================================

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def obtener_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


# =============================================================================
# Funciones JWT
# =============================================================================

def crear_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea y firma un token JWT de acceso.

    Codifica los datos del usuario (id, username, rol) junto con
    el tiempo de expiración calculado desde UTC actual.

    Args:
        data: Payload a codificar (ej: {"sub": user_id, "rol": "Vendedor"}).
        expires_delta: Tiempo de vida personalizado. Si es None,
                       usa ACCESS_TOKEN_EXPIRE_MINUTES (8h).

    Returns:
        Token JWT codificado como string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_access_token(token: str) -> dict:
    """
    Decodifica y valida un token JWT.

    Verifica la firma, la expiración y retorna el payload.
    Si el token es inválido o expiró, lanza HTTPException 401.

    Args:
        token: Token JWT a decodificar.

    Returns:
        Diccionario con el payload del token.

    Raises:
        HTTPException 401: Si el token es inválido o expiró.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
