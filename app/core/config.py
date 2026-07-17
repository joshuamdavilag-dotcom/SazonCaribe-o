from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Configuración del sistema Sazón Caribeño."""

    # Base de datos — individual vars (Render, etc.) o URL directa
    DB_HOST: str = Field(default="localhost", description="Host de la base de datos")
    DB_USER: str = Field(default="root", description="Usuario de la base de datos")
    DB_PASSWORD: str = Field(default="password", description="Contraseña de la base de datos")
    DB_NAME: str = Field(default="sazon_caribeno", description="Nombre de la base de datos")
    DB_PORT: str = Field(default="3306", description="Puerto de la base de datos")

    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="URL de conexión directa a MySQL (sobreescribe DB_* si se define)"
    )

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return self

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

    # CORS
    CORS_ORIGINS: str = Field(
        default="http://127.0.0.1:5500,http://localhost:5500",
        description="Orígenes permitidos para CORS (separados por coma)"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


@lru_cache()
def get_settings() -> Settings:
    """Obtiene una instancia caching de Settings."""
    return Settings()
