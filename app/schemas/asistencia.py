from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Turno Schemas
# =============================================================================

class TurnoBase(BaseModel):
    """Esquema base para Turno."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nombre del turno laboral",
        examples=["Mañana"]
    )
    hora_entrada: time = Field(
        ...,
        description="Hora de entrada del turno",
        examples=["08:00:00"]
    )
    hora_salida: time = Field(
        ...,
        description="Hora de salida del turno",
        examples=["16:00:00"]
    )
    horas_teoricas: int = Field(
        default=8,
        gt=0,
        description="Horas teóricas del turno",
        examples=[8]
    )


class TurnoCreate(TurnoBase):
    """Esquema para crear un Turno."""
    pass


class TurnoResponse(TurnoBase):
    """Esquema de respuesta para Turno."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del turno"
    )


# =============================================================================
# Asistencia Schemas
# =============================================================================

class AsistenciaBase(BaseModel):
    """Esquema base para Asistencia."""
    empleado_id: int = Field(
        ...,
        gt=0,
        description="ID del empleado",
        examples=[1]
    )
    turno_id: int = Field(
        ...,
        gt=0,
        description="ID del turno asignado",
        examples=[1]
    )


class AsistenciaCheckIn(BaseModel):
    """Esquema para marcar entrada de asistencia.

    La fecha y hora de entrada real se asignan en el servidor.
    """
    empleado_id: int = Field(
        ...,
        gt=0,
        description="ID del empleado que marca entrada",
        examples=[1]
    )
    turno_id: int = Field(
        ...,
        gt=0,
        description="ID del turno al que pertenece",
        examples=[1]
    )
    observaciones: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Observaciones sobre la asistencia (ej. tardanza justificada)",
        examples=["Llegó 10 minutos tarde por tema de transporte"]
    )


class AsistenciaCheckOut(BaseModel):
    """Esquema para marcar salida de asistencia.

    La hora de salida real y las horas extras se calculan en el servidor.
    """
    asistencia_id: int = Field(
        ...,
        gt=0,
        description="ID de la asistencia a finalizar",
        examples=[1]
    )
    observaciones: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Observaciones sobre la salida",
        examples=["Salida anticipada autorizada"]
    )


class AsistenciaResponse(BaseModel):
    """Esquema de respuesta para Asistencia."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único de la asistencia"
    )
    empleado_id: int = Field(
        ...,
        description="ID del empleado"
    )
    turno_id: int = Field(
        ...,
        description="ID del turno asignado"
    )
    fecha: date = Field(
        ...,
        description="Fecha de la asistencia"
    )
    hora_entrada_real: datetime = Field(
        ...,
        description="Fecha y hora real de entrada"
    )
    hora_salida_real: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora real de salida (None si aún no ha salido)"
    )
    horas_extras: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Horas extra acumuladas"
    )
    observaciones: Optional[str] = Field(
        default=None,
        description="Observaciones de la asistencia"
    )
    ip_origen: Optional[str] = Field(
        default=None,
        description="IP desde la cual se registró la entrada (auditoría)"
    )
    horas_extras_originales: Optional[Decimal] = Field(
        default=None,
        decimal_places=2,
        description="Horas extras originales antes de la última modificación (auditoría)"
    )
    motivo_modificacion: Optional[str] = Field(
        default=None,
        description="Motivo de la última modificación de horas extras"
    )
    modificado_por: Optional[int] = Field(
        default=None,
        description="ID del usuario que modificó las horas extras"
    )


class AsistenciaHorasExtrasUpdate(BaseModel):
    """Esquema para actualizar horas extras con auditoría obligatoria."""
    horas_extras: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Nuevas horas extras",
        examples=[2.50]
    )
    motivo: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Motivo del cambio (obligatorio para auditoría)",
        examples=["Corrección por turno extendido autorizado"]
    )
