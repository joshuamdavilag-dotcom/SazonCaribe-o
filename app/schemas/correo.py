"""Esquemas del módulo de correos."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DestinatarioCorreoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=200)
    activo: bool = True


class DestinatarioCorreoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, min_length=3, max_length=200)
    activo: Optional[bool] = None


class DestinatarioCorreoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    activo: bool
    creado_en: datetime


class ConfiguracionCorreoResponse(BaseModel):
    tipo: str
    nombre: str
    descripcion: str
    programado: bool
    evento: bool
    activo: bool
    hora: int
    secciones: list[str]
    secciones_disponibles: list[dict[str, Any]]
    destinatario_ids: list[int]
    actualizado_en: Optional[datetime] = None


class ConfiguracionCorreoUpdate(BaseModel):
    activo: Optional[bool] = None
    hora: Optional[int] = Field(default=None, ge=0, le=23)
    secciones: Optional[list[str]] = None
    destinatario_ids: Optional[list[int]] = None


class CorreoVistaPreviaRequest(BaseModel):
    tipo: str
    secciones: Optional[list[str]] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None


class CorreoVistaPreviaResponse(BaseModel):
    asunto: str
    html: str
    desde: date
    hasta: date
    secciones: list[str]


class CorreoEnviarRequest(BaseModel):
    tipo: str = "manual"
    asunto: Optional[str] = Field(default=None, max_length=200)
    secciones: Optional[list[str]] = None
    destinatario_ids: Optional[list[int]] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None


class CorreoPruebaRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class EnvioCorreoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    asunto: str
    estado: str
    destinatarios: list[str] = Field(default_factory=list)
    desde: Optional[str] = None
    hasta: Optional[str] = None
    error: Optional[str] = None
    intentos: int
    actor_id: Optional[int] = None
    creado_en: datetime
    enviado_en: Optional[datetime] = None


class EstadoCorreosResponse(BaseModel):
    habilitado: bool
    remitente: str
    remitente_nombre: str
    mensaje: str
    pendientes: int
    enviados: int
    errores: int
    tipos_activos: int
    total_destinatarios: int
