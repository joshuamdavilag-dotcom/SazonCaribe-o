from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Configuración del sistema Sazón Caribeño."""

    # Base de datos
    DATABASE_URL: str = Field(
        default="mysql+pymysql://root:password@localhost:3306/sazon_caribenio",
        description="URL de conexión a MySQL"
    )

    # Seguridad
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Clave secreta para JWT"
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="Algoritmo de codificación JWT"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=480,
        description="Tiempo de expiración del token en minutos"
    )

    # Servidor
    HOST: str = Field(default="0.0.0.0", description="Host del servidor")
    PORT: int = Field(default=8000, description="Puerto del servidor")
    DEBUG: bool = Field(default=True, description="Modo depuración")
    ENVIRONMENT: str = Field(default="development", description="Entorno de ejecución")

    # Heartbeat
    HEARTBEAT_INTERVAL_SECONDS: int = Field(
        default=300,
        description="Intervalo de chequeo del background task en segundos (5 min)"
    )
    HEARTBEAT_TIMEOUT_SECONDS: int = Field(
        default=900,
        description="Tiempo máximo sin heartbeat antes de finalizar turno (15 min)"
    )

    # Red
    ALLOWED_IP: str = Field(
        default="192.168.1.0/24",
        description="Rango de IPs permitidas para turnos"
    )

    # Nómina
    HOURS_PER_DAY: int = Field(default=8, description="Horas laborales por día")
    OVERTIME_MULTIPLIER: float = Field(
        default=1.0,
        description="Multiplicador horas extra (1.0 = sin recargo)"
    )

    # Impuestos — precios del menú son netos (IVA incluido, no se cobra extra)
    IVA_RATE: float = Field(default=0.0, description="Tasa de IVA — deshabilitada, precios netos")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


@lru_cache()
def get_settings() -> Settings:
    """Obtiene una instancia caching de Settings."""
    return Settings()
