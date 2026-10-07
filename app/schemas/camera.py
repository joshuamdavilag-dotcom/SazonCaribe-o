from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CameraCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre de la cámara no puede estar vacío")
        return value


class CameraUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    activa: bool | None = None

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("El nombre de la cámara no puede estar vacío")
        return value


class CameraAccessUpdate(BaseModel):
    usuario_ids: list[int] = Field(max_length=500)


class CameraResponse(BaseModel):
    id: int
    nombre: str
    slug: str
    activa: bool
    stream_url: str | None
    usuario_ids: list[int] = Field(default_factory=list)


class CameraViewerResponse(BaseModel):
    id: int
    username: str
    nombre_completo: str


class CameraStreamTokenResponse(BaseModel):
    token: str
    expira_en_segundos: int = 300
    ice_servers: list[dict[str, Any]] = Field(default_factory=list)


class CameraBridgeAuthorization(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user: str = Field(default="", max_length=100)
    password: str = Field(default="", max_length=4096)
    token: str = Field(default="", max_length=4096)
    action: str = Field(default="", max_length=20)
    path: str = Field(default="", max_length=200)


class CameraClipCreate(BaseModel):
    mime_type: str = Field(min_length=1, max_length=80)

    @field_validator("mime_type")
    @classmethod
    def validar_tipo(cls, value: str) -> str:
        mime = value.split(";", 1)[0].strip().lower()
        if mime not in {"video/webm", "video/mp4"}:
            raise ValueError("El formato debe ser video/webm o video/mp4")
        return mime


class CameraClipResponse(BaseModel):
    id: str
    camara_id: int
    camara_nombre: str
    usuario_nombre: str
    mime_type: str
    bytes_guardados: int
    creado_en: datetime
    finalizado_en: datetime


class CameraStorageResponse(BaseModel):
    clips: int
    bytes_usados: int
    bytes_libres: int
    bytes_totales: int
