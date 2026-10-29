from typing import List

from pydantic import BaseModel, Field


class PermisoItem(BaseModel):
    """Un permiso del catálogo con su estado para un usuario concreto."""

    clave: str = Field(..., description="Identificador del permiso")
    nombre: str = Field(..., description="Nombre visible del permiso")
    descripcion: str = Field(..., description="Qué permite hacer")
    grupo: str = Field(..., description="Grupo de la pantalla de permisos")
    critico: bool = Field(
        default=False,
        description="Solo un Administrador puede concederlo o quitarlo",
    )
    por_defecto: bool = Field(
        ..., description="True si el rol del usuario lo trae por defecto"
    )
    concedido: bool = Field(..., description="True si el usuario lo tiene vigente")
    editable: bool = Field(
        ..., description="True si el usuario en sesión puede cambiarlo"
    )


class CatalogoPermisosResponse(BaseModel):
    """Catálogo completo de permisos agrupado para la pantalla."""

    grupos: List[str] = Field(..., description="Orden de los grupos")
    permisos: List[PermisoItem] = Field(..., description="Todos los permisos")


class PermisosUsuarioResponse(BaseModel):
    """Estado de los permisos de un usuario."""

    usuario_id: int
    username: str
    rol: str
    es_administrador: bool = Field(
        ..., description="El Administrador siempre conserva el catálogo completo"
    )
    es_usuario_actual: bool = Field(
        ..., description="No se pueden modificar los permisos de la propia cuenta"
    )
    puede_editar: bool = Field(
        ..., description="True si el usuario en sesión puede modificar estos permisos"
    )
    motivo_bloqueo: str | None = Field(
        default=None, description="Explicación cuando la edición está bloqueada"
    )
    grupos: List[str]
    permisos: List[PermisoItem]


class ActualizarPermisosRequest(BaseModel):
    """Estado final deseado de los permisos de un usuario."""

    permisos: List[str] = Field(
        default_factory=list,
        description="Claves de permisos que el usuario debe conservar",
    )
