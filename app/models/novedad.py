from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NovedadSistema(Base):
    """Novedad publicada del sistema (control de cambios visible al equipo).

    Cada fila describe una actualización del ERP con un resumen corto y una
    lista de cambios. Las novedades se siembran desde
    ``app/core/novedades.py`` al arrancar; las que todavía no se avisaron se
    envían por Web Push a todos los usuarios.
    """

    __tablename__ = "novedades_sistema"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    version: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        comment="Identificador único de la publicación (ej: 1.2.0)",
    )
    titulo: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="Título corto de la actualización",
    )
    resumen: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="Resumen en una o dos frases para la notificación",
    )
    detalle: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Lista de cambios incluidos en la actualización",
    )
    publicada_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    notificada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True cuando el aviso push ya se envió",
    )
    notificada_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<NovedadSistema(version='{self.version}', titulo='{self.titulo}')>"
