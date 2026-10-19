import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EstadoPago(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    FALLIDO = "FALLIDO"
    CANCELADO = "CANCELADO"
    REVISION = "REVISION"


class PagoOnline(Base):
    __tablename__ = "pagos_online"
    __table_args__ = (
        UniqueConstraint("clave_idempotencia", name="uq_pagos_online_idempotencia"),
        UniqueConstraint("orden_activa_id", name="uq_pagos_online_orden_activa"),
        UniqueConstraint(
            "proveedor",
            "evento_proveedor_id",
            name="uq_pagos_online_evento_proveedor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orden_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ordenes.id", name="fk_pagos_online_orden_id"),
        nullable=False,
        index=True,
    )
    orden_activa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proveedor: Mapped[str] = mapped_column(String(40), nullable=False)
    referencia: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    clave_idempotencia: Mapped[str] = mapped_column(String(100), nullable=False)
    pago_proveedor_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    evento_proveedor_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    estado: Mapped[EstadoPago] = mapped_column(
        SAEnum(EstadoPago, name="estado_pago_online_enum", length=20),
        nullable=False,
        default=EstadoPago.PENDIENTE,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    monto_confirmado: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    moneda_confirmada: Mapped[str | None] = mapped_column(String(3), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
