from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.orden import MetodoPago
from app.models.personal import Usuario


class DivisionPagoComanda(Base):
    """División de la cantidad de un platillo entre varios comensales."""

    __tablename__ = "divisiones_pago_comanda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("ordenes.id", name="fk_divisiones_pago_orden_id"),
        nullable=False,
        index=True,
    )
    detalle_orden_id: Mapped[int] = mapped_column(
        ForeignKey("detalles_orden.id", name="fk_divisiones_pago_detalle_id"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    personas: Mapped[int] = mapped_column(Integer, nullable=False)
    inicio_cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    creada_por: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", name="fk_divisiones_pago_usuario_id"),
        nullable=False,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    pagos: Mapped[list["PagoComanda"]] = relationship(
        back_populates="division",
        cascade="all, delete-orphan",
    )
    detalle_orden: Mapped["DetalleOrden"] = relationship()


class PagoComanda(Base):
    """Pago recibido para una comanda, completo o parcial."""

    __tablename__ = "pagos_comanda"
    __table_args__ = (
        UniqueConstraint(
            "division_id",
            "parte",
            name="uq_pagos_comanda_division_parte",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orden_id: Mapped[int] = mapped_column(
        ForeignKey("ordenes.id", name="fk_pagos_comanda_orden_id"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", name="fk_pagos_comanda_usuario_id"),
        nullable=True,
    )
    metodo_pago: Mapped[MetodoPago] = mapped_column(
        SAEnum(MetodoPago, name="metodo_pago_comanda_enum", length=20),
        nullable=False,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    division_id: Mapped[int | None] = mapped_column(
        ForeignKey("divisiones_pago_comanda.id", name="fk_pagos_comanda_division_id"),
        nullable=True,
    )
    parte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cantidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    division: Mapped[DivisionPagoComanda | None] = relationship(
        back_populates="pagos"
    )
    usuario: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_id])
