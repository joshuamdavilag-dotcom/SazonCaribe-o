from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Nomina(Base):
    """Modelo de nómina quincenal del restaurante."""

    __tablename__ = "nominas"
    __table_args__ = (
        CheckConstraint(
            "salario_base_mensual > 0",
            name="ck_nominas_salario_mensual_positivo"
        ),
        CheckConstraint(
            "salario_quincenal_teorico > 0",
            name="ck_nominas_salario_quincenal_positivo"
        ),
        CheckConstraint(
            "total_horas_extras >= 0",
            name="ck_nominas_horas_extras_positivas"
        ),
        CheckConstraint(
            "pago_horas_extras >= 0",
            name="ck_nominas_pago_horas_extras_positivo"
        ),
        CheckConstraint(
            "pago_neto >= 0",
            name="ck_nominas_pago_neto_positivo"
        ),
        CheckConstraint(
            "estado IN ('PENDIENTE', 'PAGADO')",
            name="ck_nominas_estado_valido"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    empleado_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleados.id", name="fk_nominas_empleado_id"),
        nullable=False
    )
    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    fecha_fin: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    salario_base_mensual: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    salario_quincenal_teorico: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    total_horas_extras: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    pago_horas_extras: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    pago_neto: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDIENTE"
    )
    fecha_pago: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        default=None
    )

    # Relación muchos-a-uno con Empleado
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        back_populates="nominas",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Nomina(id={self.id}, empleado_id={self.empleado_id}, "
            f"periodo={self.fecha_inicio} al {self.fecha_fin}, "
            f"pago_neto={self.pago_neto}, estado='{self.estado}')>"
        )
