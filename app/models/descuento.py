import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Integer, Boolean, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TipoDescuento(str, enum.Enum):
    PORCENTAJE = "PORCENTAJE"
    MONTO = "MONTO"


class DescuentoFrecuente(Base):
    """Catálogo de descuentos predeterminados reutilizables (promos, empleados, etc.)."""

    __tablename__ = "descuentos_frecuentes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    tipo: Mapped[TipoDescuento] = mapped_column(
        SAEnum(TipoDescuento, name="tipo_descuento_enum", length=20),
        nullable=False,
        default=TipoDescuento.PORCENTAJE,
    )
    valor: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    def __repr__(self) -> str:
        return (
            f"<DescuentoFrecuente(id={self.id}, nombre='{self.nombre}', "
            f"tipo='{self.tipo.value}', valor={self.valor})>"
        )
