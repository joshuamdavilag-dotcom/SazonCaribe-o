from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class NovedadResponse(BaseModel):
    """Actualización publicada del sistema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    titulo: str
    resumen: str
    detalle: Optional[List[str]] = None
    publicada_en: datetime
    notificada: bool


class NovedadesListaResponse(BaseModel):
    """Historial de novedades más la última versión publicada."""

    novedades: List[NovedadResponse]
    ultima_version: Optional[str] = None
