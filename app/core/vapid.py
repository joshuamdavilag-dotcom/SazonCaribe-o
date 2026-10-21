"""Claves VAPID para las notificaciones Web Push.

Si el entorno no define VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY, el par de
claves se deriva de forma determinista del SECRET_KEY de la aplicación.
Ventajas:

- Las notificaciones push funcionan sin configuración manual en ningún
  entorno (producción incluida).
- Las claves no cambian entre reinicios, por lo que las suscripciones
  guardadas por los dispositivos siguen siendo válidas.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.config import get_settings

_CURVA = ec.SECP256R1()
_ORDEN_CURVA = _CURVA.group_order


def _base64url(datos: bytes) -> str:
    """Codifica bytes en base64url sin padding (formato VAPID)."""
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def derivar_claves_vapid(secret: str) -> tuple[str, str]:
    """Deriva el par de claves VAPID (p256dh) a partir de un secreto.

    Returns:
        Tupla (clave_publica, clave_privada) en base64url sin padding.
    """
    contador = 0
    while True:
        semilla = hashlib.sha256(
            f"sazoncaribeno:vapid:{contador}:{secret}".encode("utf-8")
        ).digest()
        entero = int.from_bytes(semilla, "big")
        if 1 <= entero < _ORDEN_CURVA:
            break
        contador += 1

    clave = ec.derive_private_key(entero, _CURVA)
    privada = clave.private_numbers().private_value.to_bytes(32, "big")
    publica = clave.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    return _base64url(publica), _base64url(privada)


@lru_cache(maxsize=1)
def _par_claves() -> tuple[str, bytes]:
    """Devuelve (clave_publica_base64url, clave_privada_base64url_como_bytes)."""
    settings = get_settings()
    publica = (settings.VAPID_PUBLIC_KEY or "").strip()
    privada = (settings.VAPID_PRIVATE_KEY or "").strip()
    if publica and privada:
        return publica, privada.encode("ascii")
    publica_derivada, privada_derivada = derivar_claves_vapid(settings.SECRET_KEY)
    return publica_derivada, privada_derivada.encode("ascii")


def claves_vapid() -> tuple[str, str]:
    """Devuelve (clave_publica, clave_privada) en base64url sin padding."""
    publica, privada_bytes = _par_claves()
    return publica, privada_bytes.decode("ascii")


def clave_privada_vapid() -> str:
    """Clave privada VAPID en base64url, formato que espera py-webpush."""
    _publica, privada_bytes = _par_claves()
    return privada_bytes.decode("ascii")
