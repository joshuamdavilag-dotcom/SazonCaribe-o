from datetime import datetime

from sqlalchemy import Integer, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CierreCaja(Base):
    __tablename__ = "cierres_caja"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha_cierre: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    total_ventas: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.00
    )
    total_ordenes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cerrado_por: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=True
    )

    ordenes: Mapped[list["Orden"]] = relationship(
        "Orden",
        back_populates="cierre_caja",
        lazy="selectin",
    )
