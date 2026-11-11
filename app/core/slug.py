"""Generación de slugs públicos aleatorios para la Carta Digital.

Usa ``secrets`` (criptográficamente seguro, incluido en la librería estándar):
no hace falta instalar ningún paquete externo para obtener letras y números
impredecibles.

Uso desde la terminal::

    python -m app.core.slug          # 10 caracteres
    python -m app.core.slug 14       # 14 caracteres
"""

import secrets
import string

ALFABETO = string.ascii_lowercase + string.digits
LARGO_POR_DEFECTO = 10
LARGO_MINIMO = 6
LARGO_MAXIMO = 64


def generar_slug_publico(largo: int = LARGO_POR_DEFECTO) -> str:
    """Devuelve un slug aleatorio de letras minúsculas y dígitos.

    Args:
        largo: cantidad de caracteres (entre 6 y 64).

    Returns:
        Cadena apta para una ruta URL, sin caracteres reservados.

    Raises:
        ValueError: si ``largo`` está fuera del rango permitido.
    """
    if not LARGO_MINIMO <= largo <= LARGO_MAXIMO:
        raise ValueError(
            f"El largo del slug debe estar entre {LARGO_MINIMO} y {LARGO_MAXIMO}"
        )
    return "".join(secrets.choice(ALFABETO) for _ in range(largo))


if __name__ == "__main__":
    import sys

    argumento = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        cantidad = int(argumento) if argumento else LARGO_POR_DEFECTO
    except ValueError:
        raise SystemExit(f"Largo inválido: {argumento!r}")
    print(generar_slug_publico(cantidad))
