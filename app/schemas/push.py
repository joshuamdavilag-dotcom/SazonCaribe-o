from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PushClaves(BaseModel):
    """Claves públicas que entrega el navegador al suscribirse."""

    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSuscripcionCreate(BaseModel):
    """Datos de la suscripción Web Push creada por el navegador."""

    endpoint: str = Field(min_length=10)
    keys: PushClaves


class PushDesuscripcionRequest(BaseModel):
    """Endpoint del dispositivo que se quiere dar de baja."""

    endpoint: str = Field(min_length=10)


class PushSuscripcionResponse(BaseModel):
    """Suscripción registrada de un dispositivo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint: str
    user_agent: Optional[str] = None
    creada_en: datetime
    ultimo_envio_en: Optional[datetime] = None


class PushConfigResponse(BaseModel):
    """Configuración pública de Web Push para el navegador."""

    public_key: Optional[str] = None
    habilitado: bool
    vapid_subject: str
