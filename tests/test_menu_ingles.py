"""Pruebas de los campos en inglés de la Carta Digital.

La carta de clientes se dibuja en el navegador con los datos de la API
pública, así que las traducciones viven en la base de datos:
``MenuItem.nombre_en`` / ``MenuItem.descripcion_en`` y
``CategoriaMenu.nombre_en``. Si faltan, la carta cae al texto en español.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas)
from app.schemas.menu import CategoriaMenuCreate, MenuItemCreate, MenuItemUpdate
from app.services.menu_service import MenuService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _categoria(servicio, nombre="Platos Fuertes", nombre_en=None):
    return servicio.crear_categoria(
        CategoriaMenuCreate(nombre=nombre, nombre_en=nombre_en)
    )


def test_crear_plato_guarda_los_campos_en_ingles():
    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio)

        creado = servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Arroz con Camarón",
                descripcion="Arroz marinero",
                nombre_en="Shrimp Rice",
                descripcion_en="Seafood rice",
                precio=180,
                categoria_id=categoria.id,
            )
        )

        assert creado.nombre_en == "Shrimp Rice"
        assert creado.descripcion_en == "Seafood rice"
    finally:
        db.close()


def test_actualizar_permite_borrar_la_traduccion():
    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio)
        creado = servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Sopa de Mariscos",
                nombre_en="Seafood Soup",
                precio=150,
                categoria_id=categoria.id,
            )
        )

        actualizado = servicio.actualizar_menu_item(
            creado.id, MenuItemUpdate(nombre_en=None)
        )
        assert actualizado.nombre_en is None
        assert actualizado.nombre == "Sopa de Mariscos"
    finally:
        db.close()


def test_categoria_expone_su_nombre_en_ingles():
    db = _session()
    try:
        servicio = MenuService(db)
        _categoria(servicio, nombre="Entradas", nombre_en="Starters")

        publicas = servicio.obtener_categorias_publicas()
        assert len(publicas) == 1
        assert publicas[0].nombre == "Entradas"
        assert publicas[0].nombre_en == "Starters"
    finally:
        db.close()


def test_la_carta_publica_incluye_la_traduccion_y_la_categoria():
    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio, nombre="Bebidas", nombre_en="Drinks")
        servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Jugo de Coco",
                descripcion="Natural",
                nombre_en="Coconut Juice",
                descripcion_en="Fresh",
                precio=60,
                categoria_id=categoria.id,
            )
        )

        menu = servicio.obtener_menu_publico()
        assert len(menu) == 1
        plato = menu[0]
        assert plato.nombre == "Jugo de Coco"
        assert plato.nombre_en == "Coconut Juice"
        assert plato.descripcion_en == "Fresh"
        assert plato.categoria is not None
        assert plato.categoria.nombre_en == "Drinks"
    finally:
        db.close()


def test_la_carta_publica_no_expone_recetas_ni_costos():
    """La API pública solo lleva campos de exhibición."""
    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio)
        servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Ceviche",
                precio=200,
                categoria_id=categoria.id,
            )
        )

        plato = servicio.obtener_menu_publico()[0]
        datos = plato.model_dump()
        assert "ingredientes_receta" not in datos
        assert set(datos) == {
            "id",
            "nombre",
            "descripcion",
            "nombre_en",
            "descripcion_en",
            "precio",
            "disponible",
            "imagen_url",
            "tiempo_preparacion",
            "categoria",
        }
    finally:
        db.close()


def test_sembrar_traducciones_completa_los_platos_sin_texto():
    """El arranque traduce la carta por primera vez usando el catálogo local."""
    from app.db.traducciones import sembrar_traducciones_carta

    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio, nombre="Bebidas")
        servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Café de la casa.",
                precio=20,
                categoria_id=categoria.id,
            )
        )
        servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Plato inventado de la casa",
                precio=99,
                categoria_id=categoria.id,
            )
        )

        assert sembrar_traducciones_carta(db) == 2

        menu = {plato.nombre: plato for plato in servicio.obtener_menu_publico()}
        assert menu["Café de la casa."].nombre_en == "House Coffee"
        assert menu["Café de la casa."].descripcion_en == "House coffee - 8 oz."
        assert menu["Plato inventado de la casa"].nombre_en is None

        categorias = servicio.obtener_categorias_publicas()
        assert categorias[0].nombre_en == "Drinks"
    finally:
        db.close()


def test_sembrar_traducciones_no_pisa_lo_escrito_por_el_negocio():
    """Corre en cada arranque: respeta cualquier texto ya editado."""
    from app.db.traducciones import sembrar_traducciones_carta

    db = _session()
    try:
        servicio = MenuService(db)
        categoria = _categoria(servicio, nombre="Entradas", nombre_en="Primeros")
        servicio.crear_menu_item(
            MenuItemCreate(
                nombre="Tostones con Queso",
                nombre_en="Fried Plantains",
                descripcion_en="Con queso frito",
                precio=180,
                categoria_id=categoria.id,
            )
        )

        assert sembrar_traducciones_carta(db) == 0

        plato = servicio.obtener_menu_publico()[0]
        assert plato.nombre_en == "Fried Plantains"
        assert plato.descripcion_en == "Con queso frito"
        assert servicio.obtener_categorias_publicas()[0].nombre_en == "Primeros"
    finally:
        db.close()
