import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from typing import Generator

from app.core.config import get_settings


settings = get_settings()

# SSL configuration for Render MySQL (managed databases require SSL)
connect_args = {}
if settings.ENVIRONMENT == "production":
    # Use dict-based SSL config for PyMySQL - more reliable than SSLContext in containers
    # Render's managed MySQL uses standard SSL; verify_cert=False allows connection without CA bundle
    connect_args = {
        "ssl": {
            "verify_cert": False,
            "verify_identity": False,
        }
    }

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=connect_args,
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
