"""Generación de slugs públicos aleatorios para la Carta Digital.

El formato imita los identificadores de recursos de Render
(``srv-d9cvckm7r5hc739e0kj0``): un prefijo corto, un guion y una cadena
aleatoria de letras minúsculas y dígitos.

Usa ``secrets`` (criptográficamente seguro, incluido en la librería estándar):
no hace falta instalar ningún paquete externo.

Uso desde la terminal::

    python -m app.core.slug              # web-<20 caracteres>
    python -m app.core.slug 24           # web-<24 caracteres>
    python -m app.core.slug 20 mnu       # mnu-<20 caracteres>
"""

import secrets
import string

ALFABETO = string.ascii_lowercase + string.digits
LARGO_POR_DEFECTO = 20
PREFIJO_POR_DEFECTO = "web"
LARGO_MINIMO = 8
LARGO_MAXIMO = 64
LARGO_PREFIJO_MAXIMO = 12


def generar_slug_publico(
    largo: int = LARGO_POR_DEFECTO,
    prefijo: str = PREFIJO_POR_DEFECTO,
) -> str:
    """Devuelve un slug aleatorio con formato ``prefijo-<letras y números>``.

    Args:
        largo: cantidad de caracteres aleatorios (entre 8 y 64).
        prefijo: parte fija antes del guion (solo letras y dígitos).

    Returns:
        Cadena apta para una ruta URL, sin caracteres reservados.

    Raises:
        ValueError: si ``largo`` o ``prefijo`` están fuera de lo permitido.
    """
    if not LARGO_MINIMO <= largo <= LARGO_MAXIMO:
        raise ValueError(
            f"El largo del slug debe estar entre {LARGO_MINIMO} y {LARGO_MAXIMO}"
        )
    prefijo_limpio = (prefijo or "").strip().lower()
    if (
        not prefijo_limpio
        or len(prefijo_limpio) > LARGO_PREFIJO_MAXIMO
        or not all(c in ALFABETO for c in prefijo_limpio)
    ):
        raise ValueError("El prefijo debe tener entre 1 y 12 letras o dígitos")
    cuerpo = "".join(secrets.choice(ALFABETO) for _ in range(largo))
    return f"{prefijo_limpio}-{cuerpo}"


if __name__ == "__main__":
    import sys

    argumentos = sys.argv[1:]
    try:
        cantidad = int(argumentos[0]) if argumentos else LARGO_POR_DEFECTO
    except ValueError:
        raise SystemExit(f"Largo inválido: {argumentos[0]!r}")
    prefijo = argumentos[1] if len(argumentos) > 1 else PREFIJO_POR_DEFECTO
    print(generar_slug_publico(cantidad, prefijo))
