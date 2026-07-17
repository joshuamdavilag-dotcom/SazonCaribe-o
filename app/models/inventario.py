from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, DateTime, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CategoriaInsumo(Base):
    __tablename__ = "categorias_insumo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    insumos: Mapped[List["Insumo"]] = relationship("Insumo", back_populates="categoria")

    def __repr__(self) -> str:
        return f"<CategoriaInsumo(id={self.id}, nombre='{self.nombre}')>"


class UnidadMedida(Base):
    __tablename__ = "unidades_medida"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    abreviatura: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)

    insumos: Mapped[List["Insumo"]] = relationship("Insumo", back_populates="unidad_medida_obj")

    def __repr__(self) -> str:
        return f"<UnidadMedida(id={self.id}, nombre='{self.nombre}', abrev='{self.abreviatura}')>"


class Proveedor(Base):
    """Modelo de proveedores del restaurante."""

    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    contacto_nombre: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    telefono: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Relación uno-a-muchos con Ingrediente
    ingredientes: Mapped[List["Ingrediente"]] = relationship(
        "Ingrediente",
        back_populates="proveedor",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Proveedor(id={self.id}, nombre='{self.nombre}')>"


class Ingrediente(Base):
    """Modelo de ingredientes del restaurante."""

    __tablename__ = "ingredientes"
    __table_args__ = (
        CheckConstraint(
            "stock_actual >= 0",
            name="ck_ingredientes_stock_no_negativo"
        ),
        CheckConstraint(
            "stock_minimo > 0",
            name="ck_ingredientes_stock_minimo_positivo"
        ),
    )

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
    unidad_medida: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    stock_minimo: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("5.00")
    )
    costo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Costo por unidad de medida del ingrediente (para cálculo de costos de recetas)"
    )
    proveedor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("proveedores.id", name="fk_ingredientes_proveedor_id"),
        nullable=True
    )

    # Relación muchos-a-uno con Proveedor
    proveedor: Mapped[Optional["Proveedor"]] = relationship(
        "Proveedor",
        back_populates="ingredientes",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Ingrediente(id={self.id}, nombre='{self.nombre}', "
            f"stock={self.stock_actual} {self.unidad_medida})>"
        )


class Insumo(Base):
    """Modelo de insumos/generales del inventario del restaurante."""

    __tablename__ = "insumos"
    __table_args__ = (
        CheckConstraint(
            "cantidad_actual >= 0",
            name="ck_insumos_cantidad_no_negativa"
        ),
        CheckConstraint(
            "stock_minimo > 0",
            name="ck_insumos_stock_minimo_positivo"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    cantidad_actual: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    unidad_medida_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("unidades_medida.id", name="fk_insumos_unidad_medida_id"),
        nullable=False,
    )
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("5.00"))
    categoria_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categorias_insumo.id", name="fk_insumos_categoria_id"),
        nullable=True,
    )
    costo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Costo por unidad de medida del insumo (para calculo de costos de recetas)"
    )

    unidad_medida_obj: Mapped["UnidadMedida"] = relationship("UnidadMedida", back_populates="insumos", lazy="selectin")
    categoria: Mapped[Optional["CategoriaInsumo"]] = relationship("CategoriaInsumo", back_populates="insumos", lazy="selectin")
    movimientos: Mapped[List["MovimientoInventario"]] = relationship(
        "MovimientoInventario",
        back_populates="insumo",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Insumo(id={self.id}, nombre='{self.nombre}', cantidad={self.cantidad_actual})>"


class MovimientoInventario(Base):
    """Modelo de movimientos de inventario (entradas y salidas)."""

    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('ENTRADA', 'SALIDA')",
            name="ck_movimientos_tipo_valido"
        ),
        CheckConstraint(
            "cantidad > 0",
            name="ck_movimientos_cantidad_positiva"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    insumo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("insumos.id", name="fk_movimientos_insumo_id"),
        nullable=False
    )
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    cantidad: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    motivo: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    # Relación muchos-a-uno con Insumo
    insumo: Mapped["Insumo"] = relationship(
        "Insumo",
        back_populates="movimientos",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<MovimientoInventario(id={self.id}, tipo='{self.tipo}', "
            f"cantidad={self.cantidad}, fecha={self.fecha})>"
        )
