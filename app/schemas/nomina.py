from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Nómina Schemas
# =============================================================================

class NominaGenerarRequest(BaseModel):
    """Esquema para solicitar el cálculo de nómina quincenal."""
    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio del período quincenal",
        examples=["2026-07-01"]
    )
    fecha_fin: date = Field(
        ...,
        description="Fecha de fin del período quincenal",
        examples=["2026-07-15"]
    )


class NominaCalcularRequest(BaseModel):
    """Esquema para calcular nómina de un empleado específico."""
    empleado_id: int = Field(
        ...,
        gt=0,
        description="ID del empleado",
        examples=[1]
    )
    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio del período",
        examples=["2026-07-01"]
    )
    fecha_fin: date = Field(
        ...,
        description="Fecha de fin del período",
        examples=["2026-07-15"]
    )


class NominaResponse(BaseModel):
    """Esquema de respuesta para Nómina."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del registro de nómina"
    )
    empleado_id: int = Field(
        ...,
        description="ID del empleado"
    )
    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio del período"
    )
    fecha_fin: date = Field(
        ...,
        description="Fecha de fin del período"
    )
    salario_base_mensual: Decimal = Field(
        ...,
        decimal_places=2,
        description="Salario base mensual del empleado"
    )
    salario_quincenal_teorico: Decimal = Field(
        ...,
        decimal_places=2,
        description="Salario quincenal (mensual / 2)"
    )
    total_horas_extras: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Total de horas extras en el período"
    )
    pago_horas_extras: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Monto monetario por horas extras"
    )
    total_adelantos: Decimal = Field(
        default=Decimal("0.00"),
        decimal_places=2,
        description="Total de adelantos de salario deducidos en el período"
    )
    pago_neto: Decimal = Field(
        ...,
        decimal_places=2,
        description="Pago total (salario quincenal + horas extras - adelantos)"
    )
    estado: str = Field(
        ...,
        description="Estado de la nómina (PENDIENTE, PAGADO)"
    )
    fecha_pago: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora en que se realizó el pago"
    )


# =============================================================================
# Adelanto Salario Schemas
# =============================================================================


class AdelantoSalarioCreate(BaseModel):
    """Esquema para registrar un adelanto de salario."""
    empleado_id: int = Field(
        ...,
        gt=0,
        description="ID del empleado",
        examples=[1]
    )
    monto: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Monto del adelanto",
        examples=[500.00]
    )
    observacion: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Observación o motivo del adelanto",
        examples=["Adelanto para gastos médicos"]
    )


class AdelantoSalarioResponse(BaseModel):
    """Esquema de respuesta para un adelanto de salario."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del adelanto"
    )
    empleado_id: int = Field(
        ...,
        description="ID del empleado"
    )
    monto: Decimal = Field(
        ...,
        decimal_places=2,
        description="Monto del adelanto"
    )
    fecha: datetime = Field(
        ...,
        description="Fecha y hora del registro"
    )
    observacion: Optional[str] = Field(
        default=None,
        description="Observación o motivo"
    )
    registrado_por_id: Optional[int] = Field(
        default=None,
        description="ID del usuario que registró"
    )
    gasto_id: Optional[int] = Field(
        default=None,
        description="ID del gasto generado automáticamente"
    )
