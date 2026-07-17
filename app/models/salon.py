import enum
from typing import Optional, List

from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EstadoMesa(str, enum.Enum):
    """Estados posibles para una mesa del restaurante."""
    LIBRE = "LIBRE"
    OCUPADA = "OCUPADA"
    RESERVADA = "RESERVADA"
    MANTENIMIENTO = "MANTENIMIENTO"


class Zona(Base):
    """Modelo de zonas del restaurante (Terraza, Salón, Barra, etc.)."""

    __tablename__ = "zonas"

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
    descripcion: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Relación uno-a-muchos con Mesa
    mesas: Mapped[List["Mesa"]] = relationship(
        "Mesa",
        back_populates="zona",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Zona(id={self.id}, nombre='{self.nombre}')>"


class Mesa(Base):
    """Modelo de mesas del restaurante."""

    __tablename__ = "mesas"
    __table_args__ = (
        UniqueConstraint(
            "zona_id",
            "numero",
            name="uq_mesas_zona_numero"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    numero: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    capacidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4
    )
    estado: Mapped[EstadoMesa] = mapped_column(
        SAEnum(EstadoMesa, name="estado_mesa_enum", length=20),
        nullable=False,
        default=EstadoMesa.LIBRE
    )
    zona_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("zonas.id", name="fk_mesas_zona_id"),
        nullable=False
    )

    # Relación muchos-a-uno con Zona
    zona: Mapped["Zona"] = relationship(
        "Zona",
        back_populates="mesas",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Mesa(id={self.id}, numero={self.numero}, "
            f"estado='{self.estado.value}', zona='{self.zona.nombre if self.zona else 'N/A'}')>"
        )
