from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Camera(Base):
    __tablename__ = "camaras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive
    )


class CameraAccess(Base):
    __tablename__ = "accesos_camaras"

    camara_id: Mapped[int] = mapped_column(
        ForeignKey("camaras.id", ondelete="CASCADE"), primary_key=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )


class CameraClip(Base):
    __tablename__ = "clips_camaras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camara_id: Mapped[int] = mapped_column(
        ForeignKey("camaras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="GRABANDO")
    bytes_guardados: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    siguiente_fragmento: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive, index=True
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now_naive, onupdate=_utc_now_naive
    )
    finalizado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
