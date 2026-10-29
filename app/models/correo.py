"""Modelos del módulo de correos (destinatarios, configuración y bitácora)."""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EstadoEnvio(str, enum.Enum):
    """Ciclo de vida de un envío de correo."""

    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    ERROR = "ERROR"


class DestinatarioCorreo(Base):
    """Correo de una persona que recibe los informes del negocio."""

    __tablename__ = "correos_destinatarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        return f"<DestinatarioCorreo(id={self.id}, email='{self.email}')>"


class ConfiguracionCorreo(Base):
    """Preferencias por tipo de correo: activo, secciones y destinatarios."""

    __tablename__ = "correos_configuracion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    secciones: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    destinatario_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hora: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8, server_default="8"
    )
    ultima_clave: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self) -> str:
        return f"<ConfiguracionCorreo(tipo='{self.tipo}', activo={self.activo})>"


class EnvioCorreo(Base):
    """Bitácora de cada correo preparado o enviado por el sistema."""

    __tablename__ = "correos_envios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    asunto: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoEnvio.PENDIENTE.value
    )
    html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    destinatarios: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    referencia_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    desde: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    hasta: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intentos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", name="fk_correos_envios_actor"),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    enviado_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<EnvioCorreo(id={self.id}, tipo='{self.tipo}', estado='{self.estado}')>"
