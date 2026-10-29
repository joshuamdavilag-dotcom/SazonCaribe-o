# Campos a añadir en el modelo de Mesa:
from PIL.ExifTags import Base
from alembic.environment import Optional
from pydantic import ConfigDict, Field
from pydantic.v1 import BaseModel, ConfigDict
from proto import Field
from sqlalchemy import ForeignKey, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, mapped_column

class Mesa(Base):
    """Modelo de mesa del restaurante."""

    __tablename__ = "mesas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    capacidad: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)  # Ej: 'DISPONIBLE', 'OCUPADA', 'RESERVADA'    

mesa_fusionada_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("mesas.id"), nullable=True)
color_fusion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # Ej: '#2A9D8F' o 'bg-emerald-500'

class MesaFusionada(Base):
    """Modelo para representar la relación de fusión entre mesas."""

    __tablename__ = "mesas_fusionadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mesa_principal_id: Mapped[int] = mapped_column(Integer, ForeignKey("mesas.id"), nullable=False)
    mesa_secundaria_id: Mapped[int] = mapped_column(Integer, ForeignKey("mesas.id"), nullable=False)

class MesaFusionadaSchema(BaseModel):
    """Esquema para representar la relación de fusión entre mesas."""
    model_config = ConfigDict(from_attributes=True)

    mesa_principal_id: int = Field(
        ...,
        description="ID de la mesa principal"
    )
    mesa_secundaria_id: int = Field(
        ...,
        description="ID de la mesa secundaria"
    )
    

    