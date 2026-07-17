from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.personal import RolEnum


class LoginRequest(BaseModel):
    """Esquema de entrada para el inicio de sesión."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nombre de usuario",
        examples=["admin01"]
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Contraseña en texto plano",
        examples=["micontrasena123"]
    )


class TokenResponse(BaseModel):
    """Esquema de respuesta exitosa tras la autenticación."""
    access_token: str = Field(
        ...,
        description="Token JWT de acceso"
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo de token"
    )


class TokenData(BaseModel):
    """Datos extraídos del payload de un token JWT decodificado."""
    usuario_id: Optional[int] = Field(
        default=None,
        description="ID del usuario autenticado"
    )
    username: Optional[str] = Field(
        default=None,
        description="Nombre de usuario"
    )
    rol: Optional[RolEnum] = Field(
        default=None,
        description="Rol del usuario en el sistema"
    )
