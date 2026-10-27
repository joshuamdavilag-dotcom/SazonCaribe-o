from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfiguracionSistema(Base):
    """Parámetro de configuración persistente del sistema (clave / valor).

    Se usa para ajustes que la gerencia activa o desactiva desde la UI y que
    deben sobrevivir a reinicios y redeploys, como el cierre automático de
    caja. Los valores se guardan como texto y cada servicio los interpreta.
    """

    __tablename__ = "configuracion_sistema"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    def __repr__(self) -> str:
        return f"<ConfiguracionSistema(clave='{self.clave}', valor='{self.valor}')>"
