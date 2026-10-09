from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class RegistroAuditoriaResponse(BaseModel):
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
    items: list[RegistroAuditoriaResponse]
    total: int
    limit: int
    offset: int
