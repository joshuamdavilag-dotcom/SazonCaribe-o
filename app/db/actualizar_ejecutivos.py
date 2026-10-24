"""
Actualización oficial de la categoría 🍛 Platos Ejecutivos.

Idempotente: busca cada platillo por nombre (semántica ci de MySQL, igual que el
índice único utf8mb4_0900_ai_ci) y actualiza precio, descripción y
disponible=True; si no existe bajo ese nombre, lo crea en la categoría.
Cualquier otro platillo ejecutivo previo que no esté en la lista oficial pasa a
disponible = False (borradores).

Uso:
    python -m app.db.actualizar_ejecutivos            # aplica y commitea
    python -m app.db.actualizar_ejecutivos --dry-run  # simula y hace rollback
"""
import sys
import unicodedata
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.menu import CategoriaMenu, MenuItem

NOMBRE_CATEGORIA = "🍛 Platos Ejecutivos"

DESC_POLLO_CERDO = "Acompañado con arroz, frijoles fritos, ensalada de la casa y tajadas."
DESC_PESCADO = "Acompañado con arroz, salsa rosada, ensalada de la casa y tajadas."

PLATILLOS: list[tuple[str, Decimal, str]] = [
    ("Milanesa de Pollo", Decimal("160.00"), DESC_POLLO_CERDO),
    ("Filete de Pollo a la Plancha", Decimal("130.00"), DESC_POLLO_CERDO),
    ("Filete de Pollo Empanizado", Decimal("130.00"), DESC_POLLO_CERDO),
    ("Fajitas de Pollo Salteadas", Decimal("130.00"), DESC_POLLO_CERDO),
    ("Pollo con Salsa Jalapeña", Decimal("160.00"), DESC_POLLO_CERDO),
    ("Pollo con Salsa de Hongos", Decimal("160.00"), DESC_POLLO_CERDO),
    ("Cerdo a la Plancha", Decimal("130.00"), DESC_POLLO_CERDO),
    ("Cerdo Empanizado", Decimal("130.00"), DESC_POLLO_CERDO),
    ("Cerdo con Salsa Jalapeña", Decimal("160.00"), DESC_POLLO_CERDO),
    ("Cerdo con Salsa de Hongos", Decimal("160.00"), DESC_POLLO_CERDO),
    ("Filete de Pescado a la Plancha", Decimal("160.00"), DESC_PESCADO),
    ("Filete de Pescado Empanizado", Decimal("160.00"), DESC_PESCADO),
    ("Dedos de Pescado", Decimal("160.00"), DESC_PESCADO),
]

# Platos de la lista oficial que se omiten en esta actualización (p. ej. porque
# ya existen con ese nombre en otra categoría y el índice único lo impide).
OMITIDOS: set[str] = {"Filete de Pescado a la Plancha"}


def _normalizar(nombre: str) -> str:
    """Comparación equivalente a utf8mb4_0900_ai_ci: sin mayúsculas ni tildes,
    pero distingue puntuación/letras distintas ('ñ' vs ';a', 'c' vs 'z')."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _sincronizar_ejecutivos(db: Session) -> tuple[int, int, int]:
    categoria = db.execute(
        select(CategoriaMenu).where(CategoriaMenu.nombre == NOMBRE_CATEGORIA)
    ).scalar_one()

    items = db.execute(
        select(MenuItem).where(MenuItem.categoria_id == categoria.id)
    ).scalars().all()
    por_nombre = {_normalizar(i.nombre): i for i in items}

    creados = 0
    actualizados = 0
    nombres_oficiales = {_normalizar(n) for n, _, _ in PLATILLOS}

    for nombre, precio, descripcion in PLATILLOS:
        if nombre in OMITIDOS:
            print(f"  [-] Omitido (se colocará en otra actualización): {nombre}")
            continue
        item = por_nombre.get(_normalizar(nombre))
        if item is None:
            db.add(MenuItem(
                nombre=nombre,
                precio=precio,
                descripcion=descripcion,
                disponible=True,
                categoria_id=categoria.id,
            ))
            db.flush()
            creados += 1
            print(f"  [+] Creado: {nombre} -> C${precio}")
            continue

        cambios = []
        if item.precio != precio:
            item.precio = precio
            cambios.append(f"precio C${precio}")
        if item.descripcion != descripcion:
            item.descripcion = descripcion
            cambios.append("descripcion")
        if not item.disponible:
            item.disponible = True
            cambios.append("disponible=True")
        if cambios:
            actualizados += 1
            print(f"  [~] Actualizado: {nombre} -> C${precio} ({', '.join(cambios)})")
        else:
            print(f"  [=] Sin cambios: {nombre} -> C${precio}")

    desactivados = 0
    for item in items:
        if _normalizar(item.nombre) in nombres_oficiales:
            continue
        if item.disponible:
            item.disponible = False
            desactivados += 1
            print(f"  [-] Desactivado (borrador): {item.nombre}")

    return creados, actualizados, desactivados


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db = SessionLocal()
    try:
        print(f"{'SIMULACIÓN (dry-run)' if dry_run else 'APLICANDO'} — {NOMBRE_CATEGORIA}")
        print("=" * 60)
        creados, actualizados, desactivados = _sincronizar_ejecutivos(db)
        if dry_run:
            db.rollback()
            print("=" * 60)
            print(f"[DRY-RUN] Simulado: {actualizados} actualizados, "
                  f"{creados} creados, {desactivados} desactivados (rollback).")
        else:
            db.commit()
            print("=" * 60)
            print(f"[OK] Transacción commiteada: {actualizados} actualizados, "
                  f"{creados} creados, {desactivados} desactivados (borradores).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
