from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.personal import Usuario


class PushSuscripcion(Base):
    """Suscripción Web Push (VAPID) de un dispositivo asociado a un usuario."""

    __tablename__ = "push_suscripciones"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_suscripciones_endpoint"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "usuarios.id",
            name="fk_push_suscripciones_usuario_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    endpoint: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    p256dh: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    auth: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now
    )
    ultimo_envio_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<PushSuscripcion(id={self.id}, usuario_id={self.usuario_id})>"
