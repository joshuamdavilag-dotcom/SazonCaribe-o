import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Integer, DateTime, Numeric, ForeignKey, Text, Boolean,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CategoriaGasto(str, enum.Enum):
    """Conjunto de valores válidos para la categoría de un gasto."""

    OPERATIVO = "OPERATIVO"
    MANTENIMIENTO = "MANTENIMIENTO"
    SUMINISTROS = "SUMINISTROS"
    SERVICIOS = "SERVICIOS"
    IMPUESTOS = "IMPUESTOS"
    OTROS = "OTROS"


class Gasto(Base):
    """Registro de gastos operativos del restaurante."""

    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    concepto: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    monto: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    categoria: Mapped[CategoriaGasto] = mapped_column(
        SAEnum(CategoriaGasto, name="categoria_gasto_enum", length=30),
        nullable=False,
        default=CategoriaGasto.OPERATIVO,
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    registrado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_gastos_registrado_por"),
        nullable=True,
    )
    insumo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("insumos.id", name="fk_gastos_insumo_id"),
        nullable=True,
        comment="ID del insumo si el gasto fue generado por una SALIDA de inventario",
    )
    cierre_caja_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cierres_caja.id", name="fk_gastos_cierre_caja_id"),
        nullable=True,
    )
    eliminado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Borrado lógico del gasto; excluido de listados y totales",
    )
    motivo_eliminacion: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    eliminado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_gastos_eliminado_por"),
        nullable=True,
    )
    eliminado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    cierre_caja: Mapped[Optional["CierreCaja"]] = relationship(
        "CierreCaja",
        back_populates="gastos",
    )

    def __repr__(self) -> str:
        return (
            f"<Gasto(id={self.id}, concepto='{self.concepto}', "
            f"monto={self.monto}, categoria='{self.categoria.value}')>"
        )
