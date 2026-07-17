from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Date, DateTime, Time,
    ForeignKey, Numeric, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Turno(Base):
    """Modelo de turnos laborales del restaurante."""

    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    hora_entrada: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )
    hora_salida: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )
    horas_teoricas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=8
    )

    # Relación uno-a-muchos con Asistencia
    asistencias: Mapped[List["Asistencia"]] = relationship(
        "Asistencia",
        back_populates="turno",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Turno(id={self.id}, nombre='{self.nombre}', "
            f"entrada={self.hora_entrada}, salida={self.hora_salida})>"
        )


class Asistencia(Base):
    """Modelo de asistencias diarias de los empleados."""

    __tablename__ = "asistencias"
    __table_args__ = (
        CheckConstraint(
            "horas_extras >= 0",
            name="ck_asistencias_horas_extras_positivas"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    empleado_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleados.id", name="fk_asistencias_empleado_id"),
        nullable=False
    )
    turno_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("turnos.id", name="fk_asistencias_turno_id"),
        nullable=False
    )
    fecha: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today
    )
    hora_entrada_real: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )
    hora_salida_real: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        default=None
    )
    horas_extras: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    observaciones: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )
    ip_origen: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        default=None,
        comment="IP desde la cual se registró la entrada (auditoría)"
    )
    horas_extras_originales: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,
        default=None,
        comment="Horas extras originales antes de la última modificación (auditoría)"
    )
    motivo_modificacion: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="Motivo de la última modificación de horas extras (obligatorio para auditoría)"
    )
    modificado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_asistencias_modificado_por"),
        nullable=True,
        default=None,
        comment="ID del usuario (gerente/admin) que modificó las horas extras"
    )
    ultimo_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        comment="Última vez que el cliente envió pulso de heartbeat"
    )

    # Relación muchos-a-uno con Empleado
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        back_populates="asistencias",
        lazy="selectin"
    )

    # Relación muchos-a-uno con Turno
    turno: Mapped["Turno"] = relationship(
        "Turno",
        back_populates="asistencias",
        lazy="selectin"
    )

    # Relación muchos-a-uno con Usuario (quien modificó)
    modificador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[modificado_por],
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Asistencia(id={self.id}, empleado_id={self.empleado_id}, "
            f"fecha={self.fecha}, turno_id={self.turno_id})>"
        )
