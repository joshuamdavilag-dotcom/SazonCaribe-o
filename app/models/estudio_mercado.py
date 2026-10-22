"""Modelos del módulo de Estudio de Mercado (análisis con Gemini)."""

import enum
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PeriodoEstudio(str, enum.Enum):
    """Ventana de tiempo que cubre un estudio."""

    DIA = "DIA"
    SEMANA = "SEMANA"
    MES = "MES"
    ANIO = "ANIO"


class TipoEstudio(str, enum.Enum):
    """Origen de la generación del estudio."""

    AUTOMATICO = "AUTOMATICO"
    MANUAL = "MANUAL"


class EstadoEstudio(str, enum.Enum):
    """Ciclo de vida de la generación del estudio."""

    GENERANDO = "GENERANDO"
    COMPLETADO = "COMPLETADO"
    ERROR = "ERROR"


class RolMensajeEstudio(str, enum.Enum):
    """Autor de un mensaje del chat de asesoría."""

    USUARIO = "USUARIO"
    ASISTENTE = "ASISTENTE"


class EstudioMercado(Base):
    """Documento de estudio de mercado generado por la IA."""

    __tablename__ = "estudios_mercado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    periodo: Mapped[PeriodoEstudio] = mapped_column(
        SAEnum(PeriodoEstudio, name="periodo_estudio_enum", length=20),
        nullable=False,
    )
    tipo: Mapped[TipoEstudio] = mapped_column(
        SAEnum(TipoEstudio, name="tipo_estudio_enum", length=20),
        nullable=False,
        default=TipoEstudio.MANUAL,
    )
    estado: Mapped[EstadoEstudio] = mapped_column(
        SAEnum(EstadoEstudio, name="estado_estudio_enum", length=20),
        nullable=False,
        default=EstadoEstudio.GENERANDO,
    )
    desde: Mapped[date] = mapped_column(Date, nullable=False)
    hasta: Mapped[date] = mapped_column(Date, nullable=False)
    titulo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fortalezas: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    debilidades: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    estrategias: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    analisis: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metricas: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    modelo_ia: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intentos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    notificado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    generado_por_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_estudios_mercado_generado_por"),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    completado_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EstudioMercado(id={self.id}, periodo='{self.periodo.value}', "
            f"estado='{self.estado.value}')>"
        )


class DocumentoEstudio(Base):
    """Documento (PDF/DOCX/XLSX/CSV/TXT) cargado para alimentar el análisis."""

    __tablename__ = "documentos_estudio_mercado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_archivo: Mapped[str] = mapped_column(String(20), nullable=False)
    mime: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    tamano_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    caracteres: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    subido_por_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_documentos_estudio_subido_por"),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        return f"<DocumentoEstudio(id={self.id}, nombre='{self.nombre}')>"


class MensajeEstudio(Base):
    """Mensaje del chat de asesoría (solo temas del negocio)."""

    __tablename__ = "mensajes_estudio_mercado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_mensajes_estudio_usuario"),
        nullable=True,
    )
    rol: Mapped[RolMensajeEstudio] = mapped_column(
        SAEnum(RolMensajeEstudio, name="rol_mensaje_estudio_enum", length=20),
        nullable=False,
    )
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    documento_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("documentos_estudio_mercado.id", name="fk_mensajes_estudio_documento"),
        nullable=True,
    )
    estudio_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("estudios_mercado.id", name="fk_mensajes_estudio_estudio"),
        nullable=True,
    )
    permitido: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        return f"<MensajeEstudio(id={self.id}, rol='{self.rol.value}')>"
