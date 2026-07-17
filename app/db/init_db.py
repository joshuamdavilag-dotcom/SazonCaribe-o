"""
Script de inicialización de base de datos para Sazón Caribeño.

Crea el catálogo de puestos, usuarios base para RBAC y datos de prueba
realistas para julio de 2026 (asistencia, ventas, inventario, nómina).

Uso:
  python -m app.db.init_db
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, Base
from app.core.security import obtener_password_hash
from app.models.personal import Puesto, Empleado, Usuario
from app.models.asistencia import Turno, Asistencia
from app.models.inventario import (
    Proveedor, Ingrediente, MovimientoInventario,
    CategoriaInsumo, UnidadMedida, Insumo,
)
from app.models.menu import CategoriaMenu, MenuItem, Receta
from app.models.salon import Zona, Mesa
from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.nomina import Nomina


# =============================================================================
# Catálogo de puestos por defecto
# =============================================================================

PUESTOS_SEED = [
    {"nombre": "Administrador",       "salario_base": Decimal("1200.00")},
    {"nombre": "Gerente",             "salario_base": Decimal("1000.00")},
    {"nombre": "Mesero",              "salario_base": Decimal("500.00")},
    {"nombre": "Cocinero",            "salario_base": Decimal("800.00")},
    {"nombre": "Cajero",              "salario_base": Decimal("500.00")},
    {"nombre": "Personal de Limpieza","salario_base": Decimal("400.00")},
    {"nombre": "Bartender",           "salario_base": Decimal("600.00")},
]


# =============================================================================
# Usuarios de prueba (seed básico)
# =============================================================================

USUARIOS_SEED = [
    {
        "cedula": "ADMIN-001",
        "nombre": "Admin",
        "apellido": "Sistema",
        "username": "admin",
        "password": "password123",
        "rol": "Administrador",
        "puesto_nombre": "Administrador",
    },
    {
        "cedula": "GERE-001",
        "nombre": "Gerente",
        "apellido": "Restaurante",
        "username": "gerente",
        "password": "password123",
        "rol": "Gerente",
        "puesto_nombre": "Gerente",
    },
    {
        "cedula": "MESP-001",
        "nombre": "Mesero",
        "apellido": "Principal",
        "username": "mesero",
        "password": "password123",
        "rol": "Vendedor",
        "puesto_nombre": "Mesero",
    },
]


# =============================================================================
# Datos de prueba — Julio 2026
# =============================================================================

PROVEEDORES_SEED = [
    {"nombre": "Distribuidora Mariscos del Caribe", "contacto_nombre": "Pedro Ramírez", "telefono": "300-123-4567", "email": "pedro@mariscoscaribe.com"},
    {"nombre": "Agrícola La Sierra",                "contacto_nombre": "Laura Gómez",    "telefono": "301-234-5678", "email": "laura@agricolasierra.com"},
    {"nombre": "Bebidas y Licores Tropical",        "contacto_nombre": "Miguel Torres",  "telefono": "302-345-6789", "email": "miguel@tropical.com"},
    {"nombre": "Carnes Premium C.A.",               "contacto_nombre": "Sandra López",   "telefono": "303-456-7890", "email": "sandra@carnespremium.com"},
]

CATEGORIAS_INSUMO_SEED = [
    {"nombre": "Mariscos"},
    {"nombre": "Carnes"},
    {"nombre": "Abarrotes"},
    {"nombre": "Bebidas"},
    {"nombre": "Lácteos y Huevo"},
    {"nombre": "Verduras y Frutas"},
    {"nombre": "Limpieza"},
    {"nombre": "Otros"},
]

UNIDADES_MEDIDA_SEED = [
    {"nombre": "Kilogramo",     "abreviatura": "Kg"},
    {"nombre": "Litro",         "abreviatura": "L"},
    {"nombre": "Unidad",        "abreviatura": "Un"},
    {"nombre": "Gramo",         "abreviatura": "g"},
    {"nombre": "Mililitro",     "abreviatura": "ml"},
    {"nombre": "Docena",        "abreviatura": "Doc"},
    {"nombre": "Metro",         "abreviatura": "m"},
    {"nombre": "Paquete",       "abreviatura": "Pq"},
]

ZONAS_SEED = [
    {"nombre": "Principal", "descripcion": "Salón principal del restaurante"},
    {"nombre": "Terraza",   "descripcion": "Zona de aire libre con vista al mar"},
]

TURNOS_SEED = [
    {"nombre": "Mañana", "hora_entrada": time(8, 0),  "hora_salida": time(16, 0),  "horas_teoricas": 8},
    {"nombre": "Tarde",   "hora_entrada": time(14, 0), "hora_salida": time(22, 0),  "horas_teoricas": 8},
]

INGREDIENTES_SEED = [
    {"nombre": "Camarón",          "unidad_medida": "Kg",   "costo_unitario": Decimal("35000.00"), "stock_actual": Decimal("50.00"),  "stock_minimo": Decimal("10.00"), "proveedor_idx": 0},
    {"nombre": "Pollo",            "unidad_medida": "Kg",   "costo_unitario": Decimal("12000.00"), "stock_actual": Decimal("80.00"),  "stock_minimo": Decimal("15.00"), "proveedor_idx": 3},
    {"nombre": "Arroz",            "unidad_medida": "Kg",   "costo_unitario": Decimal("4000.00"),  "stock_actual": Decimal("100.00"), "stock_minimo": Decimal("20.00"), "proveedor_idx": 1},
    {"nombre": "Limón",            "unidad_medida": "Kg",   "costo_unitario": Decimal("6000.00"),  "stock_actual": Decimal("30.00"),  "stock_minimo": Decimal("5.00"),  "proveedor_idx": 1},
    {"nombre": "Plátano",          "unidad_medida": "Kg",   "costo_unitario": Decimal("3000.00"),  "stock_actual": Decimal("40.00"),  "stock_minimo": Decimal("10.00"), "proveedor_idx": 1},
    {"nombre": "Leche de Coco",    "unidad_medida": "Litro","costo_unitario": Decimal("8000.00"),  "stock_actual": Decimal("25.00"),  "stock_minimo": Decimal("5.00"),  "proveedor_idx": 0},
    {"nombre": "Gaseosa Cola",     "unidad_medida": "Litro","costo_unitario": Decimal("4000.00"),  "stock_actual": Decimal("60.00"),  "stock_minimo": Decimal("10.00"), "proveedor_idx": 2},
    {"nombre": "Naranja",          "unidad_medida": "Kg",   "costo_unitario": Decimal("5000.00"),  "stock_actual": Decimal("35.00"),  "stock_minimo": Decimal("8.00"),  "proveedor_idx": 1},
    {"nombre": "Cebolla",          "unidad_medida": "Kg",   "costo_unitario": Decimal("3500.00"),  "stock_actual": Decimal("20.00"),  "stock_minimo": Decimal("5.00"),  "proveedor_idx": 1},
    {"nombre": "Tomate",           "unidad_medida": "Kg",   "costo_unitario": Decimal("4500.00"),  "stock_actual": Decimal("25.00"),  "stock_minimo": Decimal("5.00"),  "proveedor_idx": 1},
    {"nombre": "Ají",              "unidad_medida": "Kg",   "costo_unitario": Decimal("7000.00"),  "stock_actual": Decimal("10.00"),  "stock_minimo": Decimal("2.00"),  "proveedor_idx": 1},
    {"nombre": "Cilantro",         "unidad_medida": "Kg",   "costo_unitario": Decimal("3000.00"),  "stock_actual": Decimal("8.00"),   "stock_minimo": Decimal("2.00"),  "proveedor_idx": 1},
    {"nombre": "Pescado Fresco",   "unidad_medida": "Kg",   "costo_unitario": Decimal("28000.00"), "stock_actual": Decimal("30.00"),  "stock_minimo": Decimal("8.00"),  "proveedor_idx": 0},
    {"nombre": "Harina de Maíz",   "unidad_medida": "Kg",   "costo_unitario": Decimal("3500.00"),  "stock_actual": Decimal("40.00"),  "stock_minimo": Decimal("10.00"), "proveedor_idx": 1},
    {"nombre": "Aceite Vegetal",   "unidad_medida": "Litro","costo_unitario": Decimal("5500.00"),  "stock_actual": Decimal("20.00"),  "stock_minimo": Decimal("5.00"),  "proveedor_idx": 1},
]

INSUMOS_SEED = [
    {"nombre": "Camarón",          "unidad_medida_idx": 0, "categoria_idx": 0, "costo_unitario": Decimal("35000.00"), "cantidad_actual": Decimal("50.00"),  "stock_minimo": Decimal("10.00")},
    {"nombre": "Pollo",            "unidad_medida_idx": 0, "categoria_idx": 1, "costo_unitario": Decimal("12000.00"), "cantidad_actual": Decimal("80.00"),  "stock_minimo": Decimal("15.00")},
    {"nombre": "Arroz",            "unidad_medida_idx": 0, "categoria_idx": 2, "costo_unitario": Decimal("4000.00"),  "cantidad_actual": Decimal("100.00"), "stock_minimo": Decimal("20.00")},
    {"nombre": "Limón",            "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("6000.00"),  "cantidad_actual": Decimal("30.00"),  "stock_minimo": Decimal("5.00")},
    {"nombre": "Plátano",          "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("3000.00"),  "cantidad_actual": Decimal("40.00"),  "stock_minimo": Decimal("10.00")},
    {"nombre": "Leche de Coco",    "unidad_medida_idx": 1, "categoria_idx": 2, "costo_unitario": Decimal("8000.00"),  "cantidad_actual": Decimal("25.00"),  "stock_minimo": Decimal("5.00")},
    {"nombre": "Gaseosa Cola",     "unidad_medida_idx": 1, "categoria_idx": 3, "costo_unitario": Decimal("4000.00"),  "cantidad_actual": Decimal("60.00"),  "stock_minimo": Decimal("10.00")},
    {"nombre": "Naranja",          "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("5000.00"),  "cantidad_actual": Decimal("35.00"),  "stock_minimo": Decimal("8.00")},
    {"nombre": "Cebolla",          "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("3500.00"),  "cantidad_actual": Decimal("20.00"),  "stock_minimo": Decimal("5.00")},
    {"nombre": "Tomate",           "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("4500.00"),  "cantidad_actual": Decimal("25.00"),  "stock_minimo": Decimal("5.00")},
    {"nombre": "Ají",              "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("7000.00"),  "cantidad_actual": Decimal("10.00"),  "stock_minimo": Decimal("2.00")},
    {"nombre": "Cilantro",         "unidad_medida_idx": 0, "categoria_idx": 5, "costo_unitario": Decimal("3000.00"),  "cantidad_actual": Decimal("8.00"),   "stock_minimo": Decimal("2.00")},
    {"nombre": "Pescado Fresco",   "unidad_medida_idx": 0, "categoria_idx": 0, "costo_unitario": Decimal("28000.00"), "cantidad_actual": Decimal("30.00"),  "stock_minimo": Decimal("8.00")},
    {"nombre": "Harina de Maíz",   "unidad_medida_idx": 0, "categoria_idx": 2, "costo_unitario": Decimal("3500.00"),  "cantidad_actual": Decimal("40.00"),  "stock_minimo": Decimal("10.00")},
    {"nombre": "Aceite Vegetal",   "unidad_medida_idx": 1, "categoria_idx": 2, "costo_unitario": Decimal("5500.00"),  "cantidad_actual": Decimal("20.00"),  "stock_minimo": Decimal("5.00")},
]

CATEGORIAS_SEED = [
    {"nombre": "Mariscos",      "descripcion": "Platos principales a base de mariscos"},
    {"nombre": "Pollo y Carne", "descripcion": "Platos de pollo y carne"},
    {"nombre": "Bebidas",       "descripcion": "Bebidas frías y calientes"},
    {"nombre": "Entradas",      "descripcion": "Aperitivos y entradas"},
    {"nombre": "Postres",       "descripcion": "Postres y dulces típicos"},
]

MENU_ITEMS_SEED = [
    {"nombre": "Mariscada del Caribe",   "precio": Decimal("45000.00"), "categoria_idx": 0, "descripcion": "Langostinos, camarones, calamar y pescado al ajillo"},
    {"nombre": "Arroz con Camarón",      "precio": Decimal("38000.00"), "categoria_idx": 0, "descripcion": "Arroz marinero con camarones y coco"},
    {"nombre": "Ceviche de Camarón",     "precio": Decimal("35000.00"), "categoria_idx": 0, "descripcion": "Camarón fresco marinado en limón con cebolla y cilantro"},
    {"nombre": "Pescado Frito Entero",   "precio": Decimal("40000.00"), "categoria_idx": 0, "descripcion": "Pescado entero frito con patacón y ensalada"},
    {"nombre": "Arroz con Pollo",        "precio": Decimal("25000.00"), "categoria_idx": 1, "descripcion": "Arroz amarillo con pollo, verduras y ají"},
    {"nombre": "Pechuga a la Plancha",   "precio": Decimal("28000.00"), "categoria_idx": 1, "descripcion": "Pechuga de pollo con arroz integral y vegetales"},
    {"nombre": "Limonada Natural",       "precio": Decimal("8000.00"),  "categoria_idx": 2, "descripcion": "Limonada fresca natural"},
    {"nombre": "Gaseosa Cola",           "precio": Decimal("5000.00"),  "categoria_idx": 2, "descripcion": "Gaseosa 400ml"},
    {"nombre": "Jugo de Naranja",        "precio": Decimal("7000.00"),  "categoria_idx": 2, "descripcion": "Jugo de naranja natural recién exprimido"},
    {"nombre": "Patacón con Todo",       "precio": Decimal("20000.00"), "categoria_idx": 3, "descripcion": "Tostones rellenos de carne molida, guacamole y salsa"},
    {"nombre": "Nachos Supremos",        "precio": Decimal("18000.00"), "categoria_idx": 3, "descripcion": "Tortilla chips con queso, frijoles y pico de gallo"},
    {"nombre": "Tres Leches",            "precio": Decimal("15000.00"), "categoria_idx": 4, "descripcion": "Bizcocho bañado en tres leches con canela"},
    {"nombre": "Flan de Coco",           "precio": Decimal("12000.00"), "categoria_idx": 4, "descripcion": "Flan casero de coco con caramelo"},
]

RECETAS_SEED = [
    {"menu_item_idx": 0,  "insumo_idx": 0,  "cantidad_necesaria": Decimal("0.500")},   # Mariscada → Camarón
    {"menu_item_idx": 0,  "insumo_idx": 12, "cantidad_necesaria": Decimal("0.300")},   # Mariscada → Pescado
    {"menu_item_idx": 1,  "insumo_idx": 0,  "cantidad_necesaria": Decimal("0.400")},   # Arroz con Camarón → Camarón
    {"menu_item_idx": 1,  "insumo_idx": 2,  "cantidad_necesaria": Decimal("0.250")},   # Arroz con Camarón → Arroz
    {"menu_item_idx": 1,  "insumo_idx": 5,  "cantidad_necesaria": Decimal("0.100")},   # Arroz con Camarón → Leche de Coco
    {"menu_item_idx": 2,  "insumo_idx": 0,  "cantidad_necesaria": Decimal("0.300")},   # Ceviche → Camarón
    {"menu_item_idx": 2,  "insumo_idx": 3,  "cantidad_necesaria": Decimal("0.100")},   # Ceviche → Limón
    {"menu_item_idx": 2,  "insumo_idx": 8,  "cantidad_necesaria": Decimal("0.050")},   # Ceviche → Cebolla
    {"menu_item_idx": 2,  "insumo_idx": 11, "cantidad_necesaria": Decimal("0.020")},   # Ceviche → Cilantro
    {"menu_item_idx": 3,  "insumo_idx": 12, "cantidad_necesaria": Decimal("0.600")},   # Pescado Frito → Pescado
    {"menu_item_idx": 3,  "insumo_idx": 4,  "cantidad_necesaria": Decimal("0.300")},   # Pescado Frito → Plátano
    {"menu_item_idx": 4,  "insumo_idx": 1,  "cantidad_necesaria": Decimal("0.300")},   # Arroz con Pollo → Pollo
    {"menu_item_idx": 4,  "insumo_idx": 2,  "cantidad_necesaria": Decimal("0.200")},   # Arroz con Pollo → Arroz
    {"menu_item_idx": 4,  "insumo_idx": 10, "cantidad_necesaria": Decimal("0.030")},   # Arroz con Pollo → Ají
    {"menu_item_idx": 5,  "insumo_idx": 1,  "cantidad_necesaria": Decimal("0.250")},   # Pechuga → Pollo
    {"menu_item_idx": 5,  "insumo_idx": 2,  "cantidad_necesaria": Decimal("0.150")},   # Pechuga → Arroz
    {"menu_item_idx": 6,  "insumo_idx": 3,  "cantidad_necesaria": Decimal("0.150")},   # Limonada → Limón
    {"menu_item_idx": 7,  "insumo_idx": 6,  "cantidad_necesaria": Decimal("0.400")},   # Gaseosa → Gaseosa Cola
    {"menu_item_idx": 8,  "insumo_idx": 7,  "cantidad_necesaria": Decimal("0.300")},   # Jugo Naranja → Naranja
    {"menu_item_idx": 9,  "insumo_idx": 4,  "cantidad_necesaria": Decimal("0.400")},   # Patacón → Plátano
    {"menu_item_idx": 9,  "insumo_idx": 13, "cantidad_necesaria": Decimal("0.100")},   # Patacón → Harina
    {"menu_item_idx": 10, "insumo_idx": 13, "cantidad_necesaria": Decimal("0.150")},   # Nachos → Harina
    {"menu_item_idx": 10, "insumo_idx": 9,  "cantidad_necesaria": Decimal("0.050")},   # Nachos → Tomate
    {"menu_item_idx": 11, "insumo_idx": 5,  "cantidad_necesaria": Decimal("0.200")},   # Tres Leches → Leche de Coco
    {"menu_item_idx": 12, "insumo_idx": 5,  "cantidad_necesaria": Decimal("0.150")},   # Flan de Coco → Leche de Coco
]

EMPLEADOS_PRUEBA_SEED = [
    {
        "cedula": "ADMN-002",
        "nombre": "Carlos",
        "apellido": "Mendoza",
        "puesto_nombre": "Administrador",
        "username": "carlos",
        "password": "password123",
        "rol": "Administrador",
    },
    {
        "cedula": "COCI-001",
        "nombre": "María",
        "apellido": "González",
        "puesto_nombre": "Cocinero",
        "username": "maria",
        "password": "password123",
        "rol": "Vendedor",
    },
    {
        "cedula": "MESP-002",
        "nombre": "Juan",
        "apellido": "Pérez",
        "puesto_nombre": "Mesero",
        "username": "juan",
        "password": "password123",
        "rol": "Vendedor",
    },
    {
        "cedula": "MESP-003",
        "nombre": "Ana",
        "apellido": "López",
        "puesto_nombre": "Mesero",
        "username": "ana",
        "password": "password123",
        "rol": "Vendedor",
    },
]


# =============================================================================
# Funciones auxiliares — seeds básicos
# =============================================================================

def _seed_puestos(db: Session) -> dict[str, Puesto]:
    """
    Inserta los puestos base si la tabla está vacía.

    Returns:
        dict mapeando nombre → objeto Puesto (útil para los seeds de usuarios).
    """
    stmt = select(Puesto)
    existentes = db.execute(stmt).scalars().all()

    if existentes:
        print(f"  [=] Tabla 'puestos' ya tiene {len(existentes)} registro(s), omitiendo seed.")
        return {p.nombre: p for p in existentes}

    print("  ▸ Tabla 'puestos' vacía, insertando catálogo base...")
    mapping: dict[str, Puesto] = {}

    for data in PUESTOS_SEED:
        puesto = Puesto(**data)
        db.add(puesto)
        db.flush()
        mapping[puesto.nombre] = puesto
        print(f"    [+] {puesto.nombre:<25} → C${puesto.salario_base:,.2f}")

    return mapping


def _get_or_create_empleado(
    db: Session,
    cedula: str,
    nombre: str,
    apellido: str,
    puesto_id: int,
    salario_base: Decimal = Decimal("0"),
) -> Empleado:
    """Obtiene o crea un empleado por su cédula."""
    stmt = select(Empleado).where(Empleado.cedula_identidad == cedula)
    empleado = db.execute(stmt).scalar_one_or_none()

    if not empleado:
        empleado = Empleado(
            cedula_identidad=cedula,
            nombre=nombre,
            apellido=apellido,
            puesto_id=puesto_id,
            salario_base=salario_base,
            fecha_ingreso=date(2026, 1, 15),
            activo=True,
        )
        db.add(empleado)
        db.flush()
        print(f"    [+] Empleado: {nombre} {apellido} (id={empleado.id})")
    else:
        print(f"    [=] Empleado existente: {nombre} {apellido} (id={empleado.id})")

    return empleado


def _get_or_create_usuario(
    db: Session,
    username: str,
    password: str,
    rol: str,
    empleado_id: int,
) -> Usuario:
    """Obtiene o crea un usuario, hasheando la contraseña."""
    stmt = select(Usuario).where(Usuario.username == username)
    usuario = db.execute(stmt).scalar_one_or_none()

    if not usuario:
        usuario = Usuario(
            username=username,
            password_hash=obtener_password_hash(password),
            rol=rol,
            empleado_id=empleado_id,
            activo=True,
        )
        db.add(usuario)
        db.flush()
        print(f"    [+] Usuario: {username} | rol={rol} (id={usuario.id})")
    else:
        print(f"    [=] Usuario existente: {username} | rol={rol} (id={usuario.id})")

    return usuario


# =============================================================================
# Datos de prueba — funciones auxiliares
# =============================================================================

def _seed_proveedores(db: Session) -> list[Proveedor]:
    """Inserta proveedores base y retorna la lista ordenada."""
    stmt = select(Proveedor).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Proveedores ya existen, omitiendo.")
        return list(db.execute(select(Proveedor)).scalars().all())

    print("  ▸ Insertando proveedores...")
    proveedores = []
    for data in PROVEEDORES_SEED:
        prov = Proveedor(**data)
        db.add(prov)
        db.flush()
        proveedores.append(prov)
        print(f"    [+] {prov.nombre}")
    return proveedores


def _seed_zonas_mesas(db: Session) -> list[Mesa]:
    """Inserta zonas con mesas y retorna la lista de mesas."""
    stmt = select(Zona).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Zonas/mesas ya existen, omitiendo.")
        return list(db.execute(select(Mesa)).scalars().all())

    print("  ▸ Insertando zonas y mesas...")
    mesas = []
    mesas_por_zona = [6, 4]

    for i, zona_data in enumerate(ZONAS_SEED):
        zona = Zona(**zona_data)
        db.add(zona)
        db.flush()

        for num in range(1, mesas_por_zona[i] + 1):
            mesa = Mesa(
                numero=num,
                capacidad=random.choice([2, 4, 4, 6]),
                estado="LIBRE",
                zona_id=zona.id,
            )
            db.add(mesa)
            db.flush()
            mesas.append(mesa)
        print(f"    [+] Zona '{zona.nombre}' → {mesas_por_zona[i]} mesas")

    return mesas


def _seed_turnos(db: Session) -> dict[str, Turno]:
    """Inserta turnos base y retorna dict nombre→Turno."""
    stmt = select(Turno).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Turnos ya existen, omitiendo.")
        return {t.nombre: t for t in db.execute(select(Turno)).scalars().all()}

    print("  ▸ Insertando turnos...")
    mapping = {}
    for data in TURNOS_SEED:
        turno = Turno(**data)
        db.add(turno)
        db.flush()
        mapping[turno.nombre] = turno
        print(f"    [+] {turno.nombre}: {turno.hora_entrada}–{turno.hora_salida}")
    return mapping


def _seed_categorias_insumo(db: Session) -> list[CategoriaInsumo]:
    stmt = select(CategoriaInsumo).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Categorías de insumo ya existen, omitiendo.")
        return list(db.execute(select(CategoriaInsumo)).scalars().all())
    print("  ▸ Insertando categorías de insumo...")
    cats = []
    for data in CATEGORIAS_INSUMO_SEED:
        cat = CategoriaInsumo(**data)
        db.add(cat)
        db.flush()
        cats.append(cat)
        print(f"    [+] {cat.nombre}")
    return cats


def _seed_unidades_medida(db: Session) -> list[UnidadMedida]:
    stmt = select(UnidadMedida).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Unidades de medida ya existen, omitiendo.")
        return list(db.execute(select(UnidadMedida)).scalars().all())
    print("  ▸ Insertando unidades de medida...")
    units = []
    for data in UNIDADES_MEDIDA_SEED:
        unit = UnidadMedida(**data)
        db.add(unit)
        db.flush()
        units.append(unit)
        print(f"    [+] {unit.nombre} ({unit.abreviatura})")
    return units


def _seed_ingredientes(db: Session, proveedores: list[Proveedor]) -> list[Ingrediente]:
    """Inserta ingredientes con costo_unitario y retorna la lista."""
    stmt = select(Ingrediente).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Ingredientes ya existen, omitiendo.")
        return list(db.execute(select(Ingrediente)).scalars().all())

    print("  ▸ Insertando ingredientes...")
    ingredientes = []
    for data in INGREDIENTES_SEED:
        prov_idx = data.pop("proveedor_idx")
        ing = Ingrediente(
            **data,
            proveedor_id=proveedores[prov_idx].id if proveedores else None,
        )
        db.add(ing)
        db.flush()
        ingredientes.append(ing)
        print(f"    [+] {ing.nombre:<20} C${ing.costo_unitario:>10,.2f}/{ing.unidad_medida}")
    return ingredientes


def _seed_insumos(
    db: Session,
    unidades: list[UnidadMedida],
    cats_insumo: list[CategoriaInsumo],
) -> list[Insumo]:
    """Inserta insumos vinculados a unidades de medida y categorías."""
    stmt = select(Insumo).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Insumos ya existen, omitiendo.")
        return list(db.execute(select(Insumo)).scalars().all())

    print("  ▸ Insertando insumos...")
    insumos = []
    for data in INSUMOS_SEED:
        cat_idx = data.pop("categoria_idx")
        um_idx = data.pop("unidad_medida_idx")
        ins = Insumo(
            **data,
            unidad_medida_id=unidades[um_idx].id,
            categoria_id=cats_insumo[cat_idx].id if cats_insumo else None,
        )
        db.add(ins)
        db.flush()
        insumos.append(ins)
        print(f"    [+] {ins.nombre:<20} C${ins.costo_unitario:>10,.2f} (stock: {ins.cantidad_actual})")
    return insumos


def _seed_menu(db: Session) -> tuple[list[MenuItem], list[Receta]]:
    """Inserta categorías, items y recetas. Retorna (items, recetas)."""
    stmt = select(MenuItem).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Menú ya existe, omitiendo.")
        items = list(db.execute(select(MenuItem)).scalars().all())
        recetas = list(db.execute(select(Receta)).scalars().all())
        return items, recetas

    print("  ▸ Insertando categorías del menú...")
    categorias = []
    for data in CATEGORIAS_SEED:
        cat = CategoriaMenu(**data)
        db.add(cat)
        db.flush()
        categorias.append(cat)

    print("  ▸ Insertando items del menú...")
    items = []
    for data in MENU_ITEMS_SEED:
        cat_idx = data.pop("categoria_idx")
        item = MenuItem(**data, categoria_id=categorias[cat_idx].id)
        db.add(item)
        db.flush()
        items.append(item)
        print(f"    [+] {item.nombre:<25} C${item.precio:>10,.2f}")

    print("  ▸ Insertando recetas (insumos por plato)...")
    recetas = []
    for data in RECETAS_SEED:
        item_idx = data.pop("menu_item_idx")
        insumo_idx = data.pop("insumo_idx")
        receta = Receta(
            menu_item_id=items[item_idx].id,
            insumo_id=_seed_menu.insumos[insumo_idx].id,
            **data,
        )
        db.add(receta)
        db.flush()
        recetas.append(receta)
    print(f"    [+] {len(recetas)} recetas creadas")

    return items, recetas


def _seed_asistencias(
    db: Session,
    empleados: list[Empleado],
    turnos: dict[str, Turno],
    usuario_admin_id: int,
) -> list[Asistencia]:
    """
    Genera registros de asistencia diarios para julio 1–13, 2026.
    Incluye horas extras aleatorias y 2 registros con auditoría modificados.
    """
    stmt = select(Asistencia).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Asistencias ya existen, omitiendo.")
        return list(db.execute(select(Asistencia)).scalars().all())

    print("  ▸ Generando asistencias (1 jul – 13 jul 2026)...")
    random.seed(42)

    turno_manana = turnos["Mañana"]
    turno_tarde = turnos["Tarde"]

    fecha_inicio = date(2026, 7, 1)
    fecha_fin = date(2026, 7, 13)

    asistencias = []
    auditorias_aplicadas = 0

    for empleado in empleados:
        turno_emp = turno_manana if empleado.puesto.nombre in ("Administrador", "Cocinero") else turno_tarde

        for dia in range((fecha_fin - fecha_inicio).days + 1):
            fecha_actual = fecha_inicio + timedelta(days=dia)
            if fecha_actual.weekday() >= 5:
                continue

            entrada_minutos = random.randint(0, 15)
            h_entrada = datetime.combine(
                fecha_actual,
                time(
                    turno_emp.hora_entrada.hour,
                    turno_emp.hora_entrada.minute + entrada_minutos,
                ),
            )

            horas_extra = Decimal("0.00")
            if random.random() < 0.25:
                horas_extra = Decimal(str(random.choice([1.00, 1.50, 2.00])))

            salida_extra_minutos = int(horas_extra * 60)
            total_minutos = turno_emp.horas_teoricas * 60 + salida_extra_minutos + random.randint(-10, 20)
            h_salida = h_entrada + timedelta(minutes=total_minutos)

            asistencia = Asistencia(
                empleado_id=empleado.id,
                turno_id=turno_emp.id,
                fecha=fecha_actual,
                hora_entrada_real=h_entrada,
                hora_salida_real=h_salida,
                horas_extras=horas_extra,
                observaciones=None,
                ip_origen="192.168.0.19",
            )
            db.add(asistencia)
            db.flush()

            if auditorias_aplicadas < 2 and horas_extra >= Decimal("1.50") and empleado.nombre in ("Juan", "María"):
                original = horas_extra
                nueva = horas_extra + Decimal("1.00")
                asistencia.horas_extras_originales = original
                asistencia.horas_extras = nueva
                asistencia.motivo_modificacion = (
                    "Se quedó apoyando en limpieza de cocina por evento privado"
                    if empleado.nombre == "Juan"
                    else "Apoyo en preparación de banquete corporativo fuera de turno"
                )
                asistencia.modificado_por = usuario_admin_id
                auditorias_aplicadas += 1
                print(f"    [!] Auditoría: {empleado.nombre} {empleado.apellido} — "
                      f"horas extras {original}→{nueva} ({fecha_actual})")

            asistencias.append(asistencia)

    print(f"    [+] {len(asistencias)} registros de asistencia generados")
    random.seed()
    return asistencias


def _seed_ordenes(
    db: Session,
    mesas: list[Mesa],
    mesero_usuario_id: int,
    items: list[MenuItem],
) -> list[Orden]:
    """
    Genera órdenes pagadas diarias del 1 al 13 de julio de 2026.
    Cada día entre 3 y 8 órdenes con 1 a 4 ítems cada una.
    """
    stmt = select(Orden).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Órdenes ya existen, omitiendo.")
        return list(db.execute(select(Orden)).scalars().all())

    print("  ▸ Generando histórico de órdenes (1 jul – 13 jul 2026)...")
    random.seed(99)

    fecha_inicio = date(2026, 7, 1)
    fecha_fin = date(2026, 7, 13)

    ordenes = []
    total_detalles = 0

    for dia in range((fecha_fin - fecha_inicio).days + 1):
        fecha_actual = fecha_inicio + timedelta(days=dia)
        num_ordenes = random.randint(3, 8)

        for _ in range(num_ordenes):
            hora_venta = datetime.combine(
                fecha_actual,
                time(random.choice([11, 12, 13, 18, 19, 20]), random.randint(0, 59)),
            )

            mesa = random.choice(mesas)
            num_items = random.randint(1, 4)
            items_orden = random.sample(items, min(num_items, len(items)))

            total_orden = Decimal("0.00")
            orden = Orden(
                mesa_id=mesa.id,
                mesero_id=mesero_usuario_id,
                estado=EstadoOrden.PAGADA,
                total=Decimal("0.00"),
                fecha_creacion=hora_venta,
            )
            db.add(orden)
            db.flush()

            for item in items_orden:
                cantidad = random.randint(1, 3)
                subtotal = item.precio * cantidad
                total_orden += subtotal

                detalle = DetalleOrden(
                    orden_id=orden.id,
                    producto_id=item.id,
                    cantidad=cantidad,
                    precio_unitario=item.precio,
                )
                db.add(detalle)
                db.flush()
                total_detalles += 1

            orden.total = total_orden
            db.flush()
            ordenes.append(orden)

    print(f"    [+] {len(ordenes)} órdenes pagadas generadas ({total_detalles} detalles)")
    random.seed()
    return ordenes


def _seed_movimientos_inventario(
    db: Session,
    insumos: list[Insumo],
    ordenes: list[Orden],
):
    """
    Genera movimientos de SALIDA proporcionales a las órdenes vendidas
    y una entrada de reposición semanal.
    """
    stmt = select(MovimientoInventario).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Movimientos de inventario ya existen, omitiendo.")
        return

    print("  ▸ Generando movimientos de inventario...")

    recetas_db = list(db.execute(select(Receta)).scalars().all())
    recetas_map: dict[int, list[Receta]] = {}
    for r in recetas_db:
        recetas_map.setdefault(r.menu_item_id, []).append(r)

    total_salidas = 0
    for orden in ordenes:
        detalles_orden = list(
            db.execute(
                select(DetalleOrden).where(DetalleOrden.orden_id == orden.id)
            ).scalars().all()
        )
        for det in detalles_orden:
            recetas_producto = recetas_map.get(det.producto_id, [])
            for receta in recetas_producto:
                cantidad_total = receta.cantidad_necesaria * det.cantidad
                mv = MovimientoInventario(
                    insumo_id=receta.insumo_id,
                    tipo="SALIDA",
                    cantidad=cantidad_total,
                    motivo=f"Orden #{orden.id} — venta de producto",
                    fecha=orden.fecha_creacion + timedelta(minutes=5),
                )
                db.add(mv)
                db.flush()
                total_salidas += 1

    fechas_entradas = [date(2026, 7, 6), date(2026, 7, 13)]
    for fecha_ent in fechas_entradas:
        for ins in insumos:
            mv = MovimientoInventario(
                insumo_id=ins.id,
                tipo="ENTRADA",
                cantidad=Decimal("20.00"),
                motivo=f"Reposición semanal — {fecha_ent.strftime('%d/%m/%Y')}",
                fecha=datetime.combine(fecha_ent, time(7, 0)),
            )
            db.add(mv)
            db.flush()

    print(f"    [+] {total_salidas} salidas + {len(fechas_entradas) * len(insumos)} entradas generadas")


def _seed_nominas(db: Session, empleados: list[Empleado], asistencias: list[Asistencia]):
    """
    Genera nóminas quincenales pagadas para el período 1–15 julio 2026,
    calculando horas extras reales desde las asistencias finalizadas.
    """
    stmt = select(Nomina).limit(1)
    if db.execute(stmt).scalar_one_or_none():
        print("  [=] Nóminas ya existen, omitiendo.")
        return

    print("  ▸ Generando nóminas quincenales (1–15 jul 2026)...")

    asistencias_map: dict[int, list[Asistencia]] = {}
    for a in asistencias:
        asistencias_map.setdefault(a.empleado_id, []).append(a)

    nominas = []
    for emp in empleados:
        asistencias_emp = [
            a for a in asistencias_map.get(emp.id, [])
            if a.fecha <= date(2026, 7, 15) and a.hora_salida_real is not None
        ]

        total_ho = sum((a.horas_extras for a in asistencias_emp), Decimal("0.00"))

        salario_mensual = emp.salario_base
        salario_quincenal = salario_mensual / Decimal("2")
        tarifa_hora = salario_mensual / Decimal("30") / Decimal("8")
        pago_ho = (total_ho * tarifa_hora).quantize(Decimal("0.01"))
        bruto = salario_quincenal + pago_ho
        neto = bruto

        nomina = Nomina(
            empleado_id=emp.id,
            fecha_inicio=date(2026, 7, 1),
            fecha_fin=date(2026, 7, 15),
            salario_base_mensual=salario_mensual,
            salario_quincenal_teorico=salario_quincenal,
            total_horas_extras=total_ho,
            pago_horas_extras=pago_ho,
            pago_neto=neto,
            estado="PAGADO",
            fecha_pago=datetime(2026, 7, 16, 10, 0),
        )
        db.add(nomina)
        db.flush()
        nominas.append(nomina)
        print(f"    [+] {emp.nombre} {emp.apellido}: neto C${neto:,.2f} "
              f"(HO: {total_ho}h → C${pago_ho:,.2f})")

    print(f"    [+] {len(nominas)} nóminas generadas")


# =============================================================================
# Función principal de datos de prueba
# =============================================================================

def _seed_datos_prueba(db: Session):
    """
    Pobla la base de datos con escenario de prueba completo para julio 2026.

    Crea: proveedores, zonas/mesas, turnos, ingredientes, menú con recetas,
    4 empleados adicionales, asistencia diaria con auditorías, histórico de
    órdenes pagadas, movimientos de inventario y nóminas quincenales.
    """
    print("\n" + "=" * 55)
    print("  POBLANDO DATOS DE PRUEBA — Julio 2026")
    print("=" * 55)

    print("\n▸ Paso 1: Proveedores...")
    proveedores = _seed_proveedores(db)

    print("\n▸ Paso 2: Zonas y mesas...")
    mesas = _seed_zonas_mesas(db)

    print("\n▸ Paso 3: Turnos...")
    turnos = _seed_turnos(db)

    print("\n▸ Paso 3b: Categorías de insumo y unidades de medida...")
    cats_insumo = _seed_categorias_insumo(db)
    unidades = _seed_unidades_medida(db)

    print("\n▸ Paso 4: Ingredientes (con costo unitario)...")
    ingredientes = _seed_ingredientes(db, proveedores)

    print("\n▸ Paso 4b: Insumos (inventarios para recetas)...")
    insumos = _seed_insumos(db, unidades, cats_insumo)

    print("\n▸ Paso 5: Menú y recetas...")
    _seed_menu.insumos = insumos
    items, recetas = _seed_menu(db)

    print("\n▸ Paso 6: Empleados y usuarios de prueba...")
    puestos_map = {p.nombre: p for p in db.execute(select(Puesto)).scalars().all()}
    empleados_prueba = []
    usuarios_prueba = []

    for data in EMPLEADOS_PRUEBA_SEED:
        puesto = puestos_map.get(data["puesto_nombre"])
        if not puesto:
            print(f"    [!] Puesto '{data['puesto_nombre']}' no encontrado")
            continue

        emp = _get_or_create_empleado(
            db,
            cedula=data["cedula"],
            nombre=data["nombre"],
            apellido=data["apellido"],
            puesto_id=puesto.id,
            salario_base=puesto.salario_base,
        )
        empleados_prueba.append(emp)

        usr = _get_or_create_usuario(
            db,
            username=data["username"],
            password=data["password"],
            rol=data["rol"],
            empleado_id=emp.id,
        )
        usuarios_prueba.append(usr)

    usuario_admin = next(
        (u for u in usuarios_prueba if u.rol == "Administrador"),
        usuarios_prueba[0],
    )
    usuario_mesero = next(
        (u for u in usuarios_prueba if u.username == "juan"),
        usuarios_prueba[-1],
    )

    print("\n▸ Paso 7: Asistencias (1 jul – 13 jul 2026)...")
    asistencias = _seed_asistencias(db, empleados_prueba, turnos, usuario_admin.id)

    print("\n▸ Paso 8: Órdenes pagadas (1 jul – 13 jul 2026)...")
    ordenes = _seed_ordenes(db, mesas, usuario_mesero.id, items)

    print("\n▸ Paso 9: Movimientos de inventario...")
    _seed_movimientos_inventario(db, insumos, ordenes)

    print("\n▸ Paso 10: Nóminas quincenales (1–15 jul 2026)...")
    _seed_nominas(db, empleados_prueba, asistencias)

    print("\n" + "=" * 55)
    print("  ✓ Datos de prueba insertados correctamente")
    print("=" * 55 + "\n")


# =============================================================================
# Función principal
# =============================================================================

def init_db():
    """
    Inicializa la base de datos con puestos, usuarios y datos de prueba.

    1. Elimina y recrea todas las tablas (drop_all + create_all).
    2. Inserta los 7 puestos del catálogo base.
    3. Crea los 3 usuarios base (admin, gerente, mesero).
    4. Pobla datos de prueba para julio 2026.
    """
    print("\n" + "=" * 55)
    print("  INICIALIZACIÓN DE BASE DE DATOS — Sazón Caribeño")
    print("=" * 55)

    print("\n▸ Recreating all tables (drop_all + create_all)...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("  ✓ Tablas recreadas correctamente.\n")

    with Session(engine) as db:
        try:
            print("\n▸ Paso 1: Verificando catálogo de puestos...")
            puestos_map = _seed_puestos(db)

            print("\n▸ Paso 2: Creando empleados y usuarios base...")
            for data in USUARIOS_SEED:
                puesto = puestos_map.get(data["puesto_nombre"])
                if not puesto:
                    print(f"    [!] Puesto '{data['puesto_nombre']}' no encontrado, usando el primero disponible")
                    puesto = next(iter(puestos_map.values()))

                empleado = _get_or_create_empleado(
                    db,
                    cedula=data["cedula"],
                    nombre=data["nombre"],
                    apellido=data["apellido"],
                    puesto_id=puesto.id,
                    salario_base=puesto.salario_base,
                )
                _get_or_create_usuario(
                    db,
                    username=data["username"],
                    password=data["password"],
                    rol=data["rol"],
                    empleado_id=empleado.id,
                )

            db.commit()

            _seed_datos_prueba(db)
            db.commit()

            print("\n  Usuarios de prueba:")
            print("  ┌────────────┬──────────────┬────────────────┐")
            print("  │ Username   │ Contraseña   │ Rol            │")
            print("  ├────────────┼──────────────┼────────────────┤")
            print("  │ admin      │ password123  │ Administrador  │")
            print("  │ gerente    │ password123  │ Gerente        │")
            print("  │ mesero     │ password123  │ Vendedor       │")
            print("  │ carlos     │ password123  │ Administrador  │")
            print("  │ maria      │ password123  │ Vendedor       │")
            print("  │ juan       │ password123  │ Vendedor       │")
            print("  │ ana        │ password123  │ Vendedor       │")
            print("  └────────────┴──────────────┴────────────────┘\n")

        except Exception as e:
            db.rollback()
            print(f"\n  ✗ Error: {e}")
            raise


if __name__ == "__main__":
    init_db()
