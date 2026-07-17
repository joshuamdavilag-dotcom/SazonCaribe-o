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
    pago_neto: Decimal = Field(
        ...,
        decimal_places=2,
        description="Pago total (salario quincenal + horas extras)"
    )
    estado: str = Field(
        ...,
        description="Estado de la nómina (PENDIENTE, PAGADO)"
    )
    fecha_pago: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora en que se realizó el pago"
    )
