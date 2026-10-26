from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BackupSistema(Base):
    """Copia de seguridad del sistema almacenada dentro de la base de datos.

    Se guarda en la BD (y no en disco) porque los servicios Free de Render
    tienen sistema de archivos efímero: cualquier archivo local se pierde en
    cada redeploy, reinicio o spin-down.
    """

    __tablename__ = "backups_sistema"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    origen: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="'manual' (botón) o 'automatico' (tarea mensual)",
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creado_por: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<BackupSistema(id={self.id}, nombre='{self.nombre}', "
            f"origen='{self.origen}', registros={self.total_registros})>"
        )
