import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EstadoImportacion(str, enum.Enum):
    """Ciclo de vida de una importación de inventario."""

    ANALIZANDO = "ANALIZANDO"
    REVISION = "REVISION"
    APLICADA = "APLICADA"
    ERROR = "ERROR"


class AccionImportacion(str, enum.Enum):
    """Decisión que se tomará con una fila detectada."""

    CREAR = "CREAR"
    ACTUALIZAR = "ACTUALIZAR"
    OMITIR = "OMITIR"


class ImportacionInventario(Base):
    """Lote de inventario detectado a partir de un archivo."""

    __tablename__ = "importaciones_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_archivo: Mapped[str] = mapped_column(String(20), nullable=False)
    hash_archivo: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    estado: Mapped[EstadoImportacion] = mapped_column(
        SAEnum(EstadoImportacion), nullable=False, default=EstadoImportacion.ANALIZANDO
    )
    modelo_ia: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    resumen: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    creada_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_importaciones_creada_por"),
        nullable=True,
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    aplicada_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    detalles: Mapped[List["DetalleImportacionInventario"]] = relationship(
        "DetalleImportacionInventario",
        back_populates="importacion",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DetalleImportacionInventario.fila",
    )

    def __repr__(self) -> str:
        return (
            f"<ImportacionInventario(id={self.id}, archivo='{self.nombre_archivo}', "
            f"estado='{self.estado}')>"
        )


class DetalleImportacionInventario(Base):
    """Fila detectada dentro de una importación de inventario."""

    __tablename__ = "detalles_importacion_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    importacion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("importaciones_inventario.id", name="fk_detalles_importacion_lote"),
        nullable=False,
    )
    fila: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    texto_origen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nombre_detectado: Mapped[str] = mapped_column(String(100), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    unidad_texto: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    precio_unitario: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    precio_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    categoria_texto: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    insumo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("insumos.id", name="fk_detalles_importacion_insumo"),
        nullable=True,
    )
    accion: Mapped[AccionImportacion] = mapped_column(
        SAEnum(AccionImportacion), nullable=False, default=AccionImportacion.OMITIR
    )
    categoria_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categorias_insumo.id", name="fk_detalles_importacion_categoria"),
        nullable=True,
    )
    unidad_medida_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("unidades_medida.id", name="fk_detalles_importacion_unidad"),
        nullable=True,
    )
    unidad_empaque_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("unidades_medida.id", name="fk_detalles_importacion_empaque"),
        nullable=True,
    )
    factor_empaque: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stock_minimo: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    confianza: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    aplicado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    importacion: Mapped["ImportacionInventario"] = relationship(
        "ImportacionInventario", back_populates="detalles", lazy="selectin"
    )
    insumo: Mapped[Optional["Insumo"]] = relationship("Insumo", lazy="selectin")
    categoria: Mapped[Optional["CategoriaInsumo"]] = relationship(
        "CategoriaInsumo", lazy="selectin"
    )
    unidad_medida: Mapped[Optional["UnidadMedida"]] = relationship(
        "UnidadMedida", foreign_keys=[unidad_medida_id], lazy="selectin"
    )
    unidad_empaque: Mapped[Optional["UnidadMedida"]] = relationship(
        "UnidadMedida", foreign_keys=[unidad_empaque_id], lazy="selectin"
    )

    @property
    def insumo_nombre(self) -> Optional[str]:
        return self.insumo.nombre if self.insumo else None

    @property
    def categoria_nombre(self) -> Optional[str]:
        return self.categoria.nombre if self.categoria else self.categoria_texto

    @property
    def unidad_medida_nombre(self) -> Optional[str]:
        return self.unidad_medida.nombre if self.unidad_medida else None

    @property
    def unidad_empaque_nombre(self) -> Optional[str]:
        return self.unidad_empaque.nombre if self.unidad_empaque else None

    def __repr__(self) -> str:
        return (
            f"<DetalleImportacionInventario(id={self.id}, fila={self.fila}, "
            f"nombre='{self.nombre_detectado}')>"
        )
