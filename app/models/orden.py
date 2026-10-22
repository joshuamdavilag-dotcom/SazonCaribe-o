import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint, Boolean
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


class MetodoPago(str, enum.Enum):
    """Forma en que el cliente pagó la orden (base del análisis de métodos de pago)."""
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"
    PAGO_EN_LINEA = "PAGO_EN_LINEA"


class Orden(Base):
    """Modelo de ordenes/pedidos del restaurante."""

    __tablename__ = "ordenes"
    __table_args__ = (
        CheckConstraint(
            "total >= 0",
            name="ck_ordenes_total_no_negativo"
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_ordenes_subtotal_no_negativo"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    mesa_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("mesas.id", name="fk_ordenes_mesa_id"),
        nullable=True,
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
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    descuento_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    nombre_cliente: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    metodo_pago: Mapped[MetodoPago] = mapped_column(
        SAEnum(MetodoPago, name="metodo_pago_enum", length=20),
        nullable=False,
        default=MetodoPago.EFECTIVO,
        server_default="EFECTIVO",
        comment="Forma de pago registrada al cobrar la orden",
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
    anulada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Marca la orden como anulada (devolución total); queda en auditoría",
    )
    motivo_anulacion: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    anulada_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_ordenes_anulada_por"),
        nullable=True,
    )
    anulada_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
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
        foreign_keys=[mesero_id],
        lazy="selectin"
    )

    # Relación muchos-a-uno con Usuario (quien anuló la orden)
    anulado_por_usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[anulada_por],
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
    descuento_porcentaje: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    descuento_monto: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    motivo_descuento: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    notas: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    cantidad_devuelta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Unidades devueltas de esta línea (0 si no hubo devolución)",
    )
    motivo_devolucion: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    devuelta_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
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
