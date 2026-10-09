from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tiempo import ahora_local


class RegistroAuditoria(Base):
    __tablename__ = "registros_auditoria"
    __table_args__ = (
        Index("ix_registros_auditoria_ocurrido_en", "ocurrido_en"),
        Index("ix_registros_auditoria_accion", "accion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=ahora_local
    )
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_username: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_rol: Mapped[str] = mapped_column(String(30), nullable=False)
    accion: Mapped[str] = mapped_column(String(50), nullable=False)
    entidad_tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    entidad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    antes: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    despues: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
