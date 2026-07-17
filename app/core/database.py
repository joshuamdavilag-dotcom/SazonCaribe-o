from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from typing import Generator

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

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
