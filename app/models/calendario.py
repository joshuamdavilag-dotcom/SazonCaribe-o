from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tiempo import ahora_local


class TipoEventoCalendario(str, Enum):
    """Clases de planificación admitidas por el calendario."""

    DISPONIBILIDAD_PLATILLO = "DISPONIBILIDAD_PLATILLO"
    LLEGADA_INSUMO = "LLEGADA_INSUMO"


class EstadoEventoCalendario(str, Enum):
    """Estados de cumplimiento de un evento planificado."""

    PLANIFICADO = "PLANIFICADO"
    REALIZADO = "REALIZADO"
    CANCELADO = "CANCELADO"


class EventoCalendario(Base):
    """Evento operativo planificado, independiente del estado real del menú.

    ``fecha_fin`` y las asociaciones de catálogo son opcionales. Una
    disponibilidad se vincula a un platillo; una llegada se vincula a un
    insumo y puede indicar proveedor y cantidad prevista. El autor es
    obligatorio para conservar la trazabilidad de quién registró el plan.
    """

    __tablename__ = "eventos_calendario"
    __table_args__ = (
        Index("ix_eventos_calendario_fecha_inicio", "fecha_inicio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[TipoEventoCalendario] = mapped_column(
        SAEnum(TipoEventoCalendario, name="tipo_evento_calendario", length=30),
        nullable=False,
    )
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    color_etiqueta: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    hora_inicio: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    hora_fin: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    estado: Mapped[EstadoEventoCalendario] = mapped_column(
        SAEnum(EstadoEventoCalendario, name="estado_evento_calendario", length=20),
        nullable=False,
        default=EstadoEventoCalendario.PLANIFICADO,
    )
    menu_item_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("menu_items.id", name="fk_eventos_calendario_menu_item"),
        nullable=True,
    )
    insumo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("insumos.id", name="fk_eventos_calendario_insumo"),
        nullable=True,
    )
    proveedor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("proveedores.id", name="fk_eventos_calendario_proveedor"),
        nullable=True,
    )
    cantidad_esperada: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    creado_por_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_eventos_calendario_usuario"),
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=ahora_local,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=ahora_local,
        onupdate=ahora_local,
    )
    completado_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
