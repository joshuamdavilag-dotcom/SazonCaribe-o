import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool, StaticPool
from typing import Generator

from app.core.config import get_settings


settings = get_settings()

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if is_sqlite:
    # SQLite: check_same_thread=False para FastAPI + StaticPool para hilos
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG,
    )
    # Crear directorio de datos si no existe
    os.makedirs(os.path.dirname(settings.SQLITE_PATH) or ".", exist_ok=True)
else:
    # PostgreSQL (Render) u otro motor por URL
    connect_args = {}
    db_url = settings.DATABASE_URL
    if db_url.startswith("mysql") and settings.ENVIRONMENT == "production":
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args = {"ssl": ssl_ctx}
    elif db_url.startswith("postgres"):
        # Render exige SSL. psycopg2 espera sslmode DENTRO de la URL, no en
        # connect_args (pasarlo por connect_args revienta con 'ssl-mode').
        if "sslmode=" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{sep}sslmode=require"
    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
        echo=settings.DEBUG,
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
