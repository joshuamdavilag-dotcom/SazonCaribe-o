import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EstadoOrden(str, enum.Enum):
    """Estados posibles en el ciclo de vida de una orden."""
    PENDIENTE = "PENDIENTE"
    PREPARANDO = "PREPARANDO"
    ENTREGADA = "ENTREGADA"
    PAGADA = "PAGADA"
    CANCELADA = "CANCELADA"


class Orden(Base):
    """Modelo de ordenes/pedidos del restaurante."""

    __tablename__ = "ordenes"
    __table_args__ = (
        CheckConstraint(
            "total >= 0",
            name="ck_ordenes_total_no_negativo"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    mesa_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mesas.id", name="fk_ordenes_mesa_id"),
        nullable=False
    )
    mesero_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_ordenes_mesero_id"),
        nullable=False
    )
    estado: Mapped[EstadoOrden] = mapped_column(
        SAEnum(EstadoOrden, name="estado_orden_enum", length=20),
        nullable=False,
        default=EstadoOrden.PENDIENTE
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now
    )
    cierre_caja_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cierres_caja.id", name="fk_ordenes_cierre_caja_id"),
        nullable=True,
    )

    # Relación muchos-a-uno con Mesa
    mesa: Mapped["Mesa"] = relationship(
        "Mesa",
        lazy="selectin"
    )

    # Relación muchos-a-uno con Usuario (mesero)
    mesero: Mapped["Usuario"] = relationship(
        "Usuario",
        lazy="selectin"
    )

    # Relación uno-a-muchos con DetalleOrden
    detalles: Mapped[List["DetalleOrden"]] = relationship(
        "DetalleOrden",
        back_populates="orden",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    # Relación muchos-a-uno con CierreCaja
    cierre_caja: Mapped["CierreCaja | None"] = relationship(
        "CierreCaja",
        back_populates="ordenes",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Orden(id={self.id}, mesa_id={self.mesa_id}, "
            f"estado='{self.estado.value}', total={self.total})>"
        )


class DetalleOrden(Base):
    """Modelo de detalles (ítems) de una orden."""

    __tablename__ = "detalles_orden"
    __table_args__ = (
        CheckConstraint(
            "cantidad > 0",
            name="ck_detalles_cantidad_positiva"
        ),
        CheckConstraint(
            "precio_unitario > 0",
            name="ck_detalles_precio_positivo"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    orden_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ordenes.id", name="fk_detalles_orden_id"),
        nullable=False
    )
    producto_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("menu_items.id", name="fk_detalles_producto_id"),
        nullable=False
    )
    cantidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    notas: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )

    # Relación muchos-a-uno con Orden
    orden: Mapped["Orden"] = relationship(
        "Orden",
        back_populates="detalles",
        lazy="selectin"
    )

    # Relación muchos-a-uno con MenuItem (producto)
    producto: Mapped["MenuItem"] = relationship(
        "MenuItem",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<DetalleOrden(id={self.id}, producto_id={self.producto_id}, "
            f"cantidad={self.cantidad}, precio={self.precio_unitario})>"
        )
