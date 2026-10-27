from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local
from app.models.configuracion import ConfiguracionSistema


class ConfiguracionService:
    """Lectura y escritura de parámetros persistentes clave / valor."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, clave: str, defecto: str = "") -> str:
        """Devuelve el valor guardado o ``defecto`` si la clave no existe."""
        registro = self.db.get(ConfiguracionSistema, clave)
        return registro.valor if registro else defecto

    def guardar(self, clave: str, valor: str) -> ConfiguracionSistema:
        """Crea o actualiza el parámetro y lo deja listo para commit."""
        registro = self.db.get(ConfiguracionSistema, clave)
        if registro is None:
            registro = ConfiguracionSistema(clave=clave, valor=str(valor))
            self.db.add(registro)
        else:
            registro.valor = str(valor)
        registro.actualizado_en = ahora_local()
        self.db.flush()
        return registro

    def obtener_booleano(self, clave: str, defecto: bool = False) -> bool:
        """Interpreta el valor textual como booleano (``true``/``1``/``si``)."""
        valor = self.obtener(clave, "")
        if not valor:
            return defecto
        return valor.strip().lower() in {"1", "true", "si", "sí", "on", "activo"}

    def guardar_booleano(self, clave: str, valor: bool) -> ConfiguracionSistema:
        """Persiste un booleano como ``true`` / ``false``."""
        return self.guardar(clave, "true" if valor else "false")

    def obtener_fecha(self, clave: str) -> datetime | None:
        """Lee un datetime ISO guardado (naive) o ``None`` si no existe."""
        valor = self.obtener(clave, "")
        if not valor:
            return None
        try:
            return datetime.fromisoformat(valor)
        except ValueError:
            return None

    def listar_por_prefijo(self, prefijo: str) -> dict[str, str]:
        """Devuelve todas las claves que empiezan con ``prefijo``."""
        statement = select(ConfiguracionSistema).where(
            ConfiguracionSistema.clave.like(f"{prefijo}%")
        )
        registros = self.db.execute(statement).scalars().all()
        return {r.clave: r.valor for r in registros}
