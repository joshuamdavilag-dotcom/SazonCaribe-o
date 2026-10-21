from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Configuración del sistema Sazón Caribeño."""

    # Base de datos — PostgreSQL en Render (DATABASE_URL) o SQLite como fallback local.
    SQLITE_PATH: str = Field(
        default="./data/sazon_caribeno.db",
        description="Ruta del archivo SQLite (solo si DATABASE_URL está vacía)"
    )

    DATABASE_URL: str = Field(
        default="",
        description="URL de conexión a PostgreSQL (Render). Si está vacía se usa SQLite"
    )

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        """Normaliza DATABASE_URL y usa SQLite como fallback cuando está vacía."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Render entrega a veces el esquema 'postgres://'; SQLAlchemy exige 'postgresql://'
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]

            # MySQL/Aiven usa el parámetro '?ssl-mode=REQUIRED', que SQLAlchemy +
            # PyMySQL NO reconocen (rompen con "unexpected keyword argument
            # 'ssl-mode'"). Se elimina de la URL y el SSL se aplica vía
            # connect_args en database.py.
            if url.startswith("mysql"):
                import re
                url = re.sub(r"([?&])ssl-mode=[^&]*", r"\1", url)
                url = re.sub(r"([?&])ssl_mode=[^&]*", r"\1", url)
                # Limpiar '?' o '&' colgantes que hayan quedado
                url = re.sub(r"[?&]+$", "", url)
                url = re.sub(r"\?&", "?", url)
            self.DATABASE_URL = url
        else:
            self.DATABASE_URL = f"sqlite:///{self.SQLITE_PATH}"
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
        default=525600,
        description=(
            "Tiempo de expiración del token en minutos (525600 = 365 días). "
            "No afecta horas laborales: la sesión solo se cierra por gerencia"
        )
    )
    HARCA27_PASSWORD: Optional[str] = Field(
        default=None,
        min_length=12,
        description="Contraseña secreta para crear la cuenta administradora Harca27",
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

    # Día de negocio — corte del "hoy" laboral (los turnos de bar/restaurante cruzan medianoche)
    HORA_INICIO_DIA: int = Field(
        default=7,
        description="Hora (0-23) a la que empieza el día de negocio; el 'hoy' abarca 7:00 AM → 7:00 AM"
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

    # ImgBB — API key para almacenamiento permanente de imágenes del menú
    IMGBB_API_KEY: str = Field(
        default="",
        description="API key de ImgBB para subir imágenes de platos"
    )

    # Notificaciones push (Web Push / VAPID). Si las claves no se definen,
    # se derivan del SECRET_KEY (ver app/core/vapid.py) y el servicio funciona
    # sin configuración manual.
    VAPID_PUBLIC_KEY: str = Field(
        default="",
        description="Clave pública VAPID en base64url (opcional; si falta se deriva del SECRET_KEY)"
    )
    VAPID_PRIVATE_KEY: str = Field(
        default="",
        description="Clave privada VAPID en base64url (opcional; si falta se deriva del SECRET_KEY)"
    )
    VAPID_SUBJECT: str = Field(
        default="mailto:admin@sazoncaribeno.com",
        description="Contacto 'sub' que exige el protocolo VAPID (mailto: o https:)"
    )
    PUSH_TTL: int = Field(
        default=3600,
        description="Segundos que el servicio de push conserva la notificación"
    )
    PUSH_TIMEOUT: int = Field(
        default=15,
        description="Tiempo máximo de espera del envío push en segundos"
    )

    # Cámaras: solo se guarda el path público del stream, no las credenciales RTSP.
    CAMERA_BRIDGE_BASE_URL: str = Field(
        default="",
        description="Origen HTTPS del puente WebRTC local (sin ruta ni credenciales)"
    )
    CAMERA_STORAGE_DIR: str = Field(
        default="app/data/camera-clips",
        description="Directorio persistente para clips manuales de cámaras"
    )
    CAMERA_ICE_SERVERS_JSON: str = Field(
        default="[]",
        description="Lista JSON de servidores STUN/TURN para WebRTC"
    )
    CAMERA_TURN_SHARED_SECRET: str = Field(
        default="",
        description="Secreto compartido con TURN para generar credenciales temporales"
    )

    # Pagos en línea — permanece deshabilitado hasta registrar un adaptador real.
    PAYMENT_PROVIDER: str = Field(
        default="disabled",
        description="Proveedor de pagos activo; 'disabled' evita iniciar cobros"
    )
    PAYMENT_CURRENCY: str = Field(
        default="NIO",
        min_length=3,
        max_length=3,
        description="Moneda ISO 4217 usada para los pagos en línea"
    )
    PAYMENT_SUCCESS_URL: str = Field(
        default="",
        description="URL HTTPS de retorno tras un pago exitoso, si el proveedor la requiere"
    )
    PAYMENT_CANCEL_URL: str = Field(
        default="",
        description="URL HTTPS de retorno al cancelar checkout, si el proveedor la requiere"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        # Tolerar variables DB_* legacy (MySQL antiguo) sin romper el arranque
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Obtiene una instancia caching de Settings."""
    return Settings()
