import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from typing import Generator

from app.core.config import get_settings


settings = get_settings()

# Solo SQLite: check_same_thread=False para FastAPI + StaticPool para hilos
connect_args = {"check_same_thread": False}
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=StaticPool,
    connect_args=connect_args,
    echo=settings.DEBUG
)

# Crear directorio de datos si no existe
os.makedirs(os.path.dirname(settings.SQLITE_PATH) or ".", exist_ok=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos SQLAlchemy."""
    pass


def get_db() -> Generator:
    """Generador de sesiones de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
