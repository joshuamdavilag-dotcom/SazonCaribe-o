from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RegistroAuditoriaResponse(BaseModel):
    """Esquema de respuesta para un registro de auditoría."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ocurrido_en: datetime
    actor_id: int
    actor_username: str
    actor_rol: str
    accion: str
    entidad_tipo: str
    entidad_id: Optional[int]
    descripcion: str
    antes: Optional[dict[str, Any]]
    despues: Optional[dict[str, Any]]


class AuditoriaPageResponse(BaseModel):
    """Esquema de respuesta paginada del historial de auditoría."""
    items: list[RegistroAuditoriaResponse]
    total: int
    limit: int
    offset: int


class EliminarAuditoriaRequest(BaseModel):
    """Cuerpo para eliminar un registro de la bitácora."""

    motivo: str = Field(
        default="",
        max_length=255,
        description="Motivo obligatorio de la eliminación (queda en la bitácora)",
    )


class EliminarAuditoriaResponse(BaseModel):
    """Resultado de la eliminación de un registro de auditoría."""

    id: int
    eliminado: bool
    motivo: str
    accion_eliminada: str
