from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Text, Numeric, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CategoriaMenu(Base):
    """Modelo de categorías del menú del restaurante."""

    __tablename__ = "categorias_menu"

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

    # Relación uno-a-muchos con MenuItem
    platos: Mapped[List["MenuItem"]] = relationship(
        "MenuItem",
        back_populates="categoria",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<CategoriaMenu(id={self.id}, nombre='{self.nombre}')>"


class MenuItem(Base):
    """Modelo de platos/items del menú del restaurante."""

    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )
    descripcion: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    precio: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    disponible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    categoria_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categorias_menu.id", name="fk_menu_items_categoria_id"),
        nullable=False
    )

    # Relación muchos-a-uno con CategoriaMenu
    categoria: Mapped["CategoriaMenu"] = relationship(
        "CategoriaMenu",
        back_populates="platos",
        lazy="selectin"
    )

    # Relación uno-a-muchos con Receta
    ingredientes_receta: Mapped[List["Receta"]] = relationship(
        "Receta",
        back_populates="menu_item",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<MenuItem(id={self.id}, nombre='{self.nombre}', "
            f"precio={self.precio})>"
        )


class Receta(Base):
    """Modelo de recetas (ingredientes por plato) del restaurante."""

    __tablename__ = "recetas"
    __table_args__ = (
        UniqueConstraint(
            "menu_item_id",
            "insumo_id",
            name="uq_recetas_menu_item_insumo"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("menu_items.id", name="fk_recetas_menu_item_id"),
        nullable=False
    )
    insumo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("insumos.id", name="fk_recetas_insumo_id"),
        nullable=False
    )
    cantidad_necesaria: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False
    )

    # Relación muchos-a-uno con MenuItem
    menu_item: Mapped["MenuItem"] = relationship(
        "MenuItem",
        back_populates="ingredientes_receta",
        lazy="selectin"
    )

    # Relación muchos-a-uno con Insumo (stock real del restaurante)
    insumo: Mapped["Insumo"] = relationship(
        "Insumo",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Receta(id={self.id}, menu_item_id={self.menu_item_id}, "
            f"insumo_id={self.insumo_id}, "
            f"cantidad={self.cantidad_necesaria})>"
        )
