"""Clasificación de platillos según el nombre de su categoría.

La carta del negocio no marca las bebidas con un campo propio: la única señal
disponible es el nombre de la categoría ("Bebidas", "Tragos", "Refrescos"...).
Estas funciones viven en ``core`` porque las usan tanto el cobro por selección
como el flujo de comandas (las bebidas no pasan por cocina).
"""

import unicodedata

CATEGORIAS_BEBIDA = (
    "bebida",
    "trago",
    "coctel",
    "cocteler",
    "cerveza",
    "refresco",
    "jugo",
)


def sin_tildes(texto: str | None) -> str:
    """Devuelve el texto en minúsculas y sin acentos."""
    base = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in base if unicodedata.category(c) != "Mn").lower()


def es_categoria_bebida(nombre: str | None) -> bool:
    """Indica si el nombre de categoría corresponde a bebidas."""
    clave = sin_tildes(str(nombre or ""))
    return any(token in clave for token in CATEGORIAS_BEBIDA)
