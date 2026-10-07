from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.calendario import EstadoEventoCalendario, TipoEventoCalendario

ColorEtiquetaCalendario = Literal[
    "azul",
    "turquesa",
    "ambar",
    "rosa",
    "violeta",
    "gris",
]


class EventoCalendarioRequest(BaseModel):
    """Entrada completa para crear o reemplazar un evento del calendario.

    Las reglas de dominio aseguran fechas y horas coherentes y que los IDs
    correspondan al tipo de evento. La existencia real de los IDs se comprueba
    después en el servicio.
    """

    tipo: TipoEventoCalendario
    titulo: str = Field(min_length=1, max_length=120)
    color_etiqueta: ColorEtiquetaCalendario = "azul"
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    fecha_inicio: date
    fecha_fin: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    estado: EstadoEventoCalendario = EstadoEventoCalendario.PLANIFICADO
    menu_item_id: Optional[int] = Field(default=None, gt=0)
    insumo_id: Optional[int] = Field(default=None, gt=0)
    proveedor_id: Optional[int] = Field(default=None, gt=0)
    cantidad_esperada: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)

    @field_validator("titulo")
    @classmethod
    def validar_titulo(cls, value: str) -> str:
        """Elimina espacios externos y rechaza títulos que queden vacíos."""
        value = value.strip()
        if not value:
            raise ValueError("El título no puede quedar vacío")
        return value

    @model_validator(mode="after")
    def validar_evento(self):
        """Aplica reglas que dependen de varios campos de la solicitud."""
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha final no puede ser anterior a la fecha inicial")
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValueError("Indica ambas horas o deja el evento sin horario")
        if (
            self.hora_inicio is not None
            and self.hora_fin is not None
            and (self.fecha_fin is None or self.fecha_fin == self.fecha_inicio)
            and self.hora_fin <= self.hora_inicio
        ):
            raise ValueError("La hora final debe ser posterior a la hora inicial")

        if self.tipo == TipoEventoCalendario.DISPONIBILIDAD_PLATILLO:
            if self.menu_item_id is None:
                raise ValueError("Selecciona el platillo de disponibilidad")
            if self.insumo_id is not None or self.proveedor_id is not None or self.cantidad_esperada is not None:
                raise ValueError("Los datos de entrega solo aplican a eventos de insumos")
        elif self.tipo == TipoEventoCalendario.LLEGADA_INSUMO:
            if self.insumo_id is None:
                raise ValueError("Selecciona el insumo esperado")
            if self.menu_item_id is not None:
                raise ValueError("Una llegada de insumo no puede asociarse a un platillo")
        return self


class EventoCalendarioMasivoRequest(EventoCalendarioRequest):
    """Evento común que se aplicará únicamente a las fechas seleccionadas."""

    fecha_fin: None = None
    fechas: list[date] = Field(min_length=2, max_length=63)

    @field_validator("fechas")
    @classmethod
    def validar_fechas(cls, value: list[date]) -> list[date]:
        """Ordena las fechas y rechaza días repetidos en la selección."""
        if len(set(value)) != len(value):
            raise ValueError("No se pueden repetir fechas seleccionadas")
        return sorted(value)


class EventoCalendarioResponse(BaseModel):
    """Representación pública de un evento con nombres de catálogo resueltos."""

    id: int
    tipo: TipoEventoCalendario
    titulo: str
    color_etiqueta: Optional[str] = None
    descripcion: Optional[str]
    fecha_inicio: date
    fecha_fin: Optional[date]
    hora_inicio: Optional[time]
    hora_fin: Optional[time]
    estado: EstadoEventoCalendario
    menu_item_id: Optional[int]
    menu_item_nombre: Optional[str]
    insumo_id: Optional[int]
    insumo_nombre: Optional[str]
    insumo_unidad_medida: Optional[str]
    proveedor_id: Optional[int]
    proveedor_nombre: Optional[str]
    cantidad_esperada: Optional[Decimal]
    creado_por_id: int
    creado_en: datetime
    actualizado_en: datetime
    completado_en: Optional[datetime]


class AsistenciaCalendarioResponse(BaseModel):
    """Asistencia real en modo solo lectura para mostrarla en el calendario."""

    id: int
    empleado_id: int
    empleado_nombre: str
    turno_nombre: str
    fecha: date
    hora_entrada_real: datetime
    hora_salida_real: Optional[datetime]


class CalendarioResponse(BaseModel):
    """Respuesta mensual con planes operativos y asistencias registradas."""

    eventos: list[EventoCalendarioResponse]
    asistencias: list[AsistenciaCalendarioResponse]
