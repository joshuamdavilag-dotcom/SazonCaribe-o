"""Traducciones iniciales de la Carta Digital (español → inglés).

El archivo ``traducciones_carta.json`` acompaña a esta módulo y se usa una sola
vez: al arrancar, ``sembrar_traducciones_carta()`` rellena ``nombre_en`` /
``descripcion_en`` de los platillos que todavía no tienen traducción. A partir
de ahí la fuente de verdad es la base de datos y se edita desde Gestión de
Menú; el proceso nunca pisa un texto escrito por el negocio.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.menu import CategoriaMenu, MenuItem


RUTA_TRADUCCIONES = Path(__file__).with_name("traducciones_carta.json")

CATEGORIAS_EN = {
    "entradas": "Starters",
    "sopas": "Soups",
    "platos ejecutivos": "Executive Plates",
    "antojitos": "Appetizers",
    "platos fuertes": "Main Courses",
    "para compartir": "To Share",
    "zona caribena": "Caribbean Zone",
    "bebidas": "Drinks",
    "postres": "Desserts",
    "cafe": "Coffee",
    "acompanamientos": "Sides",
    "algo para picar": "Snacks",
    "especialidades de la casa": "House Specialties",
    "extras": "Extras",
}

_EMOJIS = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u2B00-\u2BFF]"
)


def normalizar(texto: str) -> str:
    """Clave de comparación: sin emojis, sin acentos, minúsculas."""
    limpio = _EMOJIS.sub("", texto or "")
    descompuesto = unicodedata.normalize("NFD", limpio)
    sin_tildes = "".join(
        caracter for caracter in descompuesto
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def cargar_traducciones() -> Dict[str, dict]:
    """Lee el archivo de traducciones y devuelve ``{clave_normalizada: datos}``."""
    if not RUTA_TRADUCCIONES.exists():
        return {}
    datos = json.loads(RUTA_TRADUCCIONES.read_text(encoding="utf-8"))
    return {
        normalizar(clave): valor
        for clave, valor in datos.items()
        if not clave.startswith("_") and isinstance(valor, dict)
    }


def sembrar_traducciones_carta(db: Session) -> int:
    """Completa las traducciones faltantes. Devuelve cuántos registros tocó.

    Solo escribe donde ``nombre_en`` está vacío, así que es idempotente y
    respeta cualquier traducción hecha luego desde el sistema.
    """
    traducciones = cargar_traducciones()
    if not traducciones:
        return 0

    tocados = 0

    platos = (
        db.query(MenuItem)
        .filter(or_(MenuItem.nombre_en.is_(None), MenuItem.nombre_en == ""))
        .all()
    )
    for plato in platos:
        datos = traducciones.get(normalizar(plato.nombre))
        if not datos:
            continue
        nombre_en = (datos.get("nombre") or "").strip()
        if not nombre_en:
            continue
        plato.nombre_en = nombre_en[:100]
        if not (plato.descripcion_en or "").strip():
            descripcion_en = (datos.get("descripcion") or "").strip()
            plato.descripcion_en = descripcion_en or None
        tocados += 1

    categorias = (
        db.query(CategoriaMenu)
        .filter(or_(CategoriaMenu.nombre_en.is_(None), CategoriaMenu.nombre_en == ""))
        .all()
    )
    for categoria in categorias:
        nombre_en = CATEGORIAS_EN.get(normalizar(categoria.nombre))
        if not nombre_en:
            continue
        categoria.nombre_en = nombre_en[:50]
        tocados += 1

    if tocados:
        db.commit()

    return tocados
