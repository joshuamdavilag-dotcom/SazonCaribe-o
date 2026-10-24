"""
Script de reestructuración COMPLETA del menú de Sazón Caribeño.

Reemplaza el menú actual por el formato nuevo (8 categorías con emoji y
platillos renovados) sin romper el historial de órdenes:

1. Borrón y cuenta nueva: marca TODOS los platillos actuales como
   ``disponible = False`` (borrado lógico que preserva el historial).
2. Registra las 8 categorías nuevas con sus emojis oficiales.
3. Reasigna/elimina categorías viejas que no coincidan con las nuevas.
4. Inserta o reactiva los platillos nuevos con ``disponible = True``;
   si un platillo coincide por nombre exacto, actualiza categoría,
   precio y descripción sin perder recetas ni imagen.

Idempotente: se puede ejecutar varias veces sin generar duplicados.

Uso:
  python -m app.db.restructurar_menu
"""

import unicodedata
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.menu import CategoriaMenu, MenuItem


# =============================================================================
# Nuevas categorías del menú (con emojis oficiales)
# =============================================================================

NUEVAS_CATEGORIAS = [
    "⭐ Especialidades de la Casa",
    "🌊 Zona Caribeña",
    "🍽️ Platos Fuertes",
    "🍛 Platos Ejecutivos",
    "🍗 Para Compartir",
    "🍻 Algo para Picar",
    "➕ Extras",
    "🍹 Bebidas",
]

# Categorías viejas conocidas → categoría nueva que las reemplaza.
# Cualquier categoría vieja no mapeada se reasigna a CATEGORIA_FALLBACK.
REASIGNACION_CATEGORIAS = {
    # Categorías del seed original (init_db.py)
    "Mariscos": "🌊 Zona Caribeña",
    "Pollo y Carne": "🍽️ Platos Fuertes",
    "Bebidas": "🍹 Bebidas",
    "Entradas": "🍻 Algo para Picar",
    "Postres": "⭐ Especialidades de la Casa",
    # Categorías del menú de producción anterior
    "Plato ejecutivo": "🍛 Platos Ejecutivos",
    "Plato Fuerte": "🍽️ Platos Fuertes",
    "Sopas": "🍽️ Platos Fuertes",
    "Para Compartir": "🍗 Para Compartir",
    "Extras": "➕ Extras",
    "Ceviches": "🌊 Zona Caribeña",
    "Empaques": "🍗 Para Compartir",
    "Gaseosas": "🍹 Bebidas",
    "Cervezas": "🍹 Bebidas",
    "Frescos naturales": "🍹 Bebidas",
    "Café": "🍹 Bebidas",
}

CATEGORIA_FALLBACK = "🍽️ Platos Fuertes"


def _normalizar(nombre: str) -> str:
    """
    Normaliza un nombre para compararlo sin distinguir mayúsculas ni acentos.

    La base de datos usa el collation ``utf8mb4_0900_ai_ci`` (insensible a
    mayúsculas y acentos) tanto en el índice único como en las comparaciones,
    por lo que el matching en Python debe replicar ese comportamiento.
    """
    return (
        unicodedata.normalize("NFKD", nombre)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )

# =============================================================================
# Platillos nuevos — (categoría, nombre, precio C$, descripción)
# =============================================================================

PLATILLOS = [
    # ------------------------- 🍛 Platos Ejecutivos -------------------------
    ("🍛 Platos Ejecutivos", "Milanesa de pollo a la plancha", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Filete de pollo a la plancha", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Fajitas de pollo", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Pollo en salsa jalapeño", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Filete de cerdo a la plancha", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Cerdo adobado", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Fajitas de cerdo en salsa", Decimal("120.00"),
     "Acompañamiento: arroz, frijoles fritos, ensalada de lechuga, plátanos o chips."),
    ("🍛 Platos Ejecutivos", "Filete de res a la plancha", Decimal("140.00"),
     "Acompañamiento: arroz, frijoles licuados, papa salteada, ensalada de lechuga, plátano frito o chips."),
    ("🍛 Platos Ejecutivos", "Asaditos de res", Decimal("140.00"),
     "Acompañamiento: arroz, frijoles licuados, papa salteada, ensalada de lechuga, plátano frito o chips."),
    ("🍛 Platos Ejecutivos", "Bisteck en salsa jalapeña", Decimal("140.00"),
     "Acompañamiento: arroz, frijoles licuados, papa salteada, ensalada de lechuga, plátano frito o chips."),
    ("🍛 Platos Ejecutivos", "Tortas de carne en salsa", Decimal("140.00"),
     "Acompañamiento: arroz, frijoles licuados, papa salteada, ensalada de lechuga, plátano frito o chips."),
    ("🍛 Platos Ejecutivos", "Fajitas salteadas de res", Decimal("140.00"),
     "Acompañamiento: arroz, frijoles licuados, papa salteada, ensalada de lechuga, plátano frito o chips."),
    ("🍛 Platos Ejecutivos", "Chuleta de pescado empanizado", Decimal("140.00"),
     None),
    ("🍛 Platos Ejecutivos", "Dedos de pescado empanizado", Decimal("140.00"),
     None),

    # --------------------- ⭐ Especialidades de la Casa ----------------------
    ("⭐ Especialidades de la Casa", "Arroz con camarones de la casa", Decimal("160.00"),
     "Acompañamiento: arroz, lechuga, patatas o chips. Aguacate (solo en temporada)."),
    ("⭐ Especialidades de la Casa", "Filete de pescado al vapor", Decimal("160.00"),
     "Acompañamiento: arroz, lechuga, patatas o chips. Aguacate (solo en temporada)."),
    ("⭐ Especialidades de la Casa", "Pescado entero frito", Decimal("160.00"),
     "Acompañamiento: arroz, lechuga, patatas o chips. Aguacate (solo en temporada)."),

    # --------------------------- 🍗 Para Compartir ---------------------------
    ("🍗 Para Compartir", "Nachos de pollo", Decimal("290.00"),
     "Chips, frijoles molidos, trozos de pollo, queso mozzarella, lechuga chifonada, crema, pico de gallo, queso cheddar y rodajas de jalapeño."),
    ("🍗 Para Compartir", "Nachos de res", Decimal("320.00"),
     "Chips, frijoles molidos, trozos de res, queso mozzarella, lechuga chifonada y pico de gallo."),
    ("🍗 Para Compartir", "Chilaquiles de pollo", Decimal("300.00"),
     "Chips bañadas en salsa roja, pollo desmenuzado, queso mozzarella, crema, queso rallado, acompañado de salsa especial y jalapeño."),
    ("🍗 Para Compartir", "Bandeja de alas", Decimal("570.00"),
     "12 unidades de alas de pollo, papas fritas, 4 salsas: BBQ, Búfalo, Ranch, Salsa de tomate. Bastones de apio y zanahoria."),
    ("🍗 Para Compartir", "Canasta caribeña", Decimal("350.00"),
     "6 unidades de canasta de plátano, salsa especial, camarones, queso gratinado, cebolla encurtida, pico de gallo y chile criollo."),
    ("🍗 Para Compartir", "Canasta mixta", Decimal("350.00"),
     "6 unidades de canasta de plátano, frijoles molidos, pollo, cerdo, res, queso gratinado, pico de gallo y dulce criollo."),
    ("🍗 Para Compartir", "Brocheta caribeña", Decimal("280.00"),
     "Queso asado, trozos de res, camarones y vegetales, acompañado de pico de gallo y salsa especial."),

    # --------------------------- 🍽️ Platos Fuertes ---------------------------
    ("🍽️ Platos Fuertes", "Churrasco argentino", Decimal("410.00"),
     "Acompañado con: arroz, queso asado, ensalada de lechuga, chorizo parrillero, tostones o papas fritas y chimichurri."),
    ("🍽️ Platos Fuertes", "Camarones al gusto (Empanizados, al ajillo o a la diabla)", Decimal("450.00"),
     "Acompañado con arroz, vegetales salteados, ensalada de lechuga, papas fritas."),
    ("🍽️ Platos Fuertes", "Arroz con camarones tradicional", Decimal("300.00"),
     "Acompañado con: ensalada de lechuga, papas fritas o tostones y salsa de la casa."),
    ("🍽️ Platos Fuertes", "Filete de pollo con salsa jalapeña", Decimal("260.00"),
     "Arroz, ensalada de lechuga, tostones o papas fritas, y nuestra salsa especial jalapeña."),
    ("🍽️ Platos Fuertes", "Costillas de cerdo", Decimal("300.00"),
     "Arroz, ensalada de lechuga, papas fritas o tostones, vegetales salteados."),
    ("🍽️ Platos Fuertes", "Fettuccini en salsa con pollo", Decimal("300.00"),
     "Pasta fettuccini, pollo en trozos, queso parmesano."),

    # --------------------------- 🌊 Zona Caribeña ----------------------------
    ("🌊 Zona Caribeña", "Ceviche mi sazón", Decimal("200.00"),
     "Trozos de pescado fresco, vegetales, lechuga, plátano, salsa de la casa."),
    ("🌊 Zona Caribeña", "Ceviche tropical", Decimal("220.00"),
     "Trozos de pescado frito, salsa especial, vegetales, plátanos."),
    ("🌊 Zona Caribeña", "Coctel de camarón", Decimal("300.00"),
     "Camarones, salsa rosada, vegetales, plátanos."),
    ("🌊 Zona Caribeña", "Coctel de camarón y pescado", Decimal("350.00"),
     "Camarones y trozos de pescado, vegetales y plátanos."),
    ("🌊 Zona Caribeña", "Rondón de pescado", Decimal("450.00"),
     "Verduras, plátano verde, pescado y leche de coco tradicional."),

    # --------------------------- 🍻 Algo para Picar --------------------------
    ("🍻 Algo para Picar", "Alitas picantes o barbacoa", Decimal("350.00"),
     "6 unidades con papas fritas y bastones de apio y zanahoria."),
    ("🍻 Algo para Picar", "Chunks de pollo", Decimal("320.00"),
     "12 porciones con papas fritas, bastones de apio y zanahoria."),
    ("🍻 Algo para Picar", "Quesadilla de pollo", Decimal("260.00"),
     "Tortilla de harina, pollo salteado, queso gratinado, salsa rosada y pico de gallo."),
    ("🍻 Algo para Picar", "Burrito de pollo o res", Decimal("300.00"),
     "Tortilla de harina, pollo o res salteado, queso gratinado, lechuga, pico de gallo, salsas y papas fritas."),
    ("🍻 Algo para Picar", "Cazuela mixta", Decimal("200.00"),
     "Queso fundido, chorizo criollo, frijoles molidos y chips."),
    ("🍻 Algo para Picar", "Hamburguesa clásica", Decimal("230.00"),
     "Tomate, lechuga, cebolla morada, salsa, carne, queso y papas fritas."),
    ("🍻 Algo para Picar", "Hamburguesa Jack Daniel's", Decimal("320.00"),
     "Cebolla morada, bacon, queso amarillo, salsa especial, pepinillo y papas fritas."),
    ("🍻 Algo para Picar", "Patty caribeño", Decimal("230.00"),
     "6 unidades de empanadas rellenas de carne de res y salsa roja."),
    ("🍻 Algo para Picar", "Tajadas con pollo", Decimal("200.00"),
     "Tajadas, filete de pollo, ensalada y pico de gallo."),
    ("🍻 Algo para Picar", "Tajadas con res", Decimal("220.00"),
     "Filete de res, tajadas, ensalada y pico de gallo."),
    ("🍻 Algo para Picar", "Dedos de pollo", Decimal("200.00"),
     None),
    ("🍻 Algo para Picar", "Dedos de queso", Decimal("180.00"),
     None),

    # ------------------------------- ➕ Extras -------------------------------
    ("➕ Extras", "Extra Arroz", Decimal("25.00"), None),
    ("➕ Extras", "Extra Ensalada", Decimal("30.00"), None),
    ("➕ Extras", "Extra Vegetales", Decimal("40.00"), None),
    ("➕ Extras", "Extra Tajadas", Decimal("30.00"), None),
    ("➕ Extras", "Extra Tostones", Decimal("30.00"), None),
    ("➕ Extras", "Extra Papas Fritas", Decimal("80.00"), None),
    ("➕ Extras", "Extra Salsas", Decimal("40.00"), None),
    ("➕ Extras", "Extra Chile criollo", Decimal("25.00"), None),
    ("➕ Extras", "Extra Frijoles molidos", Decimal("40.00"), None),
    ("➕ Extras", "Extra Frijoles Fritos", Decimal("25.00"), None),
    ("➕ Extras", "Extra Queso mozzarella", Decimal("60.00"), None),
    ("➕ Extras", "Extra Jalapeños", Decimal("20.00"), None),
    ("➕ Extras", "Café de cortesía", Decimal("20.00"), None),
]


# =============================================================================
# Pasos
# =============================================================================

def _bloquear_platos_actuales(db: Session) -> int:
    """
    Paso 1 — Borrón y cuenta nueva.

    Marca TODOS los platillos actuales como ``disponible = False``
    (borrado lógico para preservar el historial de órdenes).
    """
    items = db.execute(select(MenuItem)).scalars().all()
    desactivados = 0
    for item in items:
        if item.disponible:
            item.disponible = False
            desactivados += 1
    print(f"  ▸ Platillos desactivados (disponible = False): {desactivados}")
    return desactivados


def _crear_categorias_nuevas(db: Session) -> dict[str, CategoriaMenu]:
    """
    Paso 2 — Registro de categorías nuevas con emojis oficiales.

    Crea las categorías que falten y conserva las que ya existan con el
    mismo nombre exacto.
    """
    existentes = {
        c.nombre: c for c in db.execute(select(CategoriaMenu)).scalars().all()
    }
    categorias: dict[str, CategoriaMenu] = {}

    for nombre in NUEVAS_CATEGORIAS:
        if nombre in existentes:
            categorias[nombre] = existentes[nombre]
            print(f"  [=] Categoría existente: {nombre}")
        else:
            categoria = CategoriaMenu(nombre=nombre)
            db.add(categoria)
            db.flush()
            categorias[nombre] = categoria
            print(f"  [+] Categoría creada: {nombre}")

    return categorias


def _limpiar_categorias_viejas(
    db: Session,
    categorias_nuevas: dict[str, CategoriaMenu],
) -> int:
    """
    Paso 2b — Elimina las categorías viejas que no coinciden con las nuevas.

    Sus platillos (ya inactivos) se reasignan a la categoría nueva que las
    reemplaza según REASIGNACION_CATEGORIAS (o CATEGORIA_FALLBACK) para
    respetar la FK no nullable de menu_items.
    """
    nombres_nuevos = set(categorias_nuevas.keys())
    todas = db.execute(select(CategoriaMenu)).scalars().all()

    ids_a_eliminar: list[int] = []
    eliminadas = 0
    for categoria in todas:
        if categoria.nombre in nombres_nuevos:
            continue

        destino_nombre = REASIGNACION_CATEGORIAS.get(categoria.nombre)
        if destino_nombre is None:
            print(f"  [!] Categoría vieja sin mapeo '{categoria.nombre}' → {CATEGORIA_FALLBACK}")
            destino_nombre = CATEGORIA_FALLBACK
        destino = categorias_nuevas[destino_nombre]

        platos = db.execute(
            select(MenuItem).where(MenuItem.categoria_id == categoria.id)
        ).scalars().all()
        for plato in platos:
            plato.categoria_id = destino.id
            print(f"    [~] {plato.nombre} → {destino.nombre}")

        ids_a_eliminar.append(categoria.id)
        eliminadas += 1
        print(f"  [-] Categoría vieja a eliminar: {categoria.nombre} "
              f"({len(platos)} platos reasignados)")

    db.flush()

    if ids_a_eliminar:
        db.execute(
            delete(CategoriaMenu).where(CategoriaMenu.id.in_(ids_a_eliminar))
        )
        db.flush()
        print(f"  [x] {eliminadas} categorías viejas eliminadas")

    return eliminadas


def _sincronizar_platillos(
    db: Session,
    categorias: dict[str, CategoriaMenu],
) -> tuple[int, int]:
    """
    Paso 3 — Inserción de platillos (formato nuevo).

    Si ya existe un platillo con el mismo nombre exacto, actualiza su
    categoría, precio y descripción, y lo reactiva (disponible = True).
    En caso contrario crea el platillo nuevo activo.
    """
    existentes = {
        _normalizar(p.nombre): p for p in db.execute(select(MenuItem)).scalars().all()
    }

    creados = 0
    actualizados = 0

    for cat_nombre, nombre, precio, descripcion in PLATILLOS:
        categoria = categorias[cat_nombre]
        plato = existentes.get(_normalizar(nombre))

        if plato:
            plato.categoria_id = categoria.id
            plato.precio = precio
            plato.descripcion = descripcion
            plato.disponible = True
            actualizados += 1
            print(f"  [~] Reactivado: {nombre} → C${precio:,.2f} ({cat_nombre})")
        else:
            nuevo = MenuItem(
                nombre=nombre,
                precio=precio,
                descripcion=descripcion,
                disponible=True,
                categoria_id=categoria.id,
            )
            db.add(nuevo)
            db.flush()
            creados += 1
            print(f"  [+] Creado: {nombre} → C${precio:,.2f} ({cat_nombre})")

    return creados, actualizados


def _resumen(db: Session) -> None:
    """Imprime el resumen final del menú por categoría."""
    print("\n" + "=" * 55)
    print("  RESUMEN DEL MENÚ NUEVO")
    print("=" * 55)

    for categoria in db.execute(
        select(CategoriaMenu).order_by(CategoriaMenu.id)
    ).scalars().all():
        activos = db.execute(
            select(MenuItem).where(
                MenuItem.categoria_id == categoria.id,
                MenuItem.disponible.is_(True),
            )
        ).scalars().all()
        total = db.execute(
            select(MenuItem).where(MenuItem.categoria_id == categoria.id)
        ).scalars().all()
        print(f"  {categoria.nombre:<28} activos: {len(activos):>3} "
              f"(total: {len(total)})")

    total_activos = db.execute(
        select(MenuItem).where(MenuItem.disponible.is_(True))
    ).scalars().all()
    total_inactivos = db.execute(
        select(MenuItem).where(MenuItem.disponible.is_(False))
    ).scalars().all()
    print("-" * 55)
    print(f"  TOTAL activos: {len(total_activos)} | "
          f"inactivos (historial): {len(total_inactivos)}")
    print("=" * 55 + "\n")


# =============================================================================
# Función principal
# =============================================================================

def restructurar_menu():
    """
    Reestructura completamente el menú del restaurante.

    1. Desactiva todos los platillos actuales (borrado lógico).
    2. Crea/actualiza las 8 categorías nuevas con emojis.
    3. Elimina las categorías viejas no contempladas.
    4. Inserta o reactiva los platillos nuevos (disponible = True).

    Todo se ejecuta en una sola transacción: si algo falla se hace
    rollback y el menú queda intacto.
    """
    print("\n" + "=" * 55)
    print("  REESTRUCTURACIÓN DEL MENÚ — Sazón Caribeño")
    print("=" * 55)

    with Session(engine) as db:
        try:
            print("\n▸ Paso 1: Borrón y cuenta nueva (desactivar platillos actuales)...")
            _bloquear_platos_actuales(db)

            print("\n▸ Paso 2: Categorías nuevas con emojis...")
            categorias = _crear_categorias_nuevas(db)

            print("\n▸ Paso 2b: Limpieza de categorías viejas...")
            _limpiar_categorias_viejas(db, categorias)

            print("\n▸ Paso 3: Platillos nuevos (insertar o reactivar)...")
            creados, actualizados = _sincronizar_platillos(db, categorias)

            db.commit()
            print(f"\n  ✓ Menú reestructurado: {creados} creados, "
                  f"{actualizados} reactivados/actualizados.")

            _resumen(db)

        except Exception as e:
            db.rollback()
            print(f"\n  ✗ Error: {e}")
            raise


if __name__ == "__main__":
    restructurar_menu()
