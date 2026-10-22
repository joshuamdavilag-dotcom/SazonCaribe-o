"""Schemas del módulo de Estudio de Mercado."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.estudio_mercado import (
    EstadoEstudio,
    PeriodoEstudio,
    RolMensajeEstudio,
    TipoEstudio,
)


class GenerarEstudioRequest(BaseModel):
    """Solicitud manual de un estudio de mercado."""

    periodo: PeriodoEstudio = Field(
        default=PeriodoEstudio.MES,
        description="Ventana de análisis: DIA, SEMANA, MES o ANIO",
    )


class EstudioMercadoResponse(BaseModel):
    """Estudio generado, con el análisis estructurado y sus métricas."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    periodo: PeriodoEstudio
    tipo: TipoEstudio
    estado: EstadoEstudio
    desde: date
    hasta: date
    titulo: Optional[str] = None
    resumen: Optional[str] = None
    fortalezas: Optional[list] = None
    debilidades: Optional[list] = None
    estrategias: Optional[list] = None
    analisis: Optional[dict[str, Any]] = None
    metricas: Optional[dict[str, Any]] = None
    modelo_ia: Optional[str] = None
    error: Optional[str] = None
    intentos: int = 0
    generado_por_id: Optional[int] = None
    creado_en: datetime
    completado_en: Optional[datetime] = None


class DocumentoEstudioResponse(BaseModel):
    """Documento cargado para alimentar el análisis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo_archivo: str
    mime: Optional[str] = None
    tamano_bytes: int = 0
    caracteres: int = 0
    subido_por_id: Optional[int] = None
    creado_en: datetime


class MensajeEstudioResponse(BaseModel):
    """Mensaje del chat de asesoría."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rol: RolMensajeEstudio
    contenido: str
    documento_id: Optional[int] = None
    estudio_id: Optional[int] = None
    permitido: bool = True
    creado_en: datetime


class ConsultaEstudioRequest(BaseModel):
    """Pregunta dirigida al asesor de IA."""

    mensaje: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Consulta sobre el negocio o sobre el uso del sistema",
        examples=["¿Qué platillos dejan más margen este mes?"],
    )
    documento_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Documento adjunto que la IA debe leer para responder",
    )


class ConsultaEstudioResponse(BaseModel):
    """Respuesta del asesor, con la marca de alcance."""

    permitido: bool = Field(
        ...,
        description="False cuando la consulta estaba fuera del alcance del negocio",
    )
    respuesta: str
    mensaje_id: int
