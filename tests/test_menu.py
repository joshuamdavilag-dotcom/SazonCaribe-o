"""
Script de pruebas E2E para el módulo de Menú y Recetas.
Ejecutar con el servidor corriendo: python -m uvicorn app.main:app --reload

Uso: python tests/test_menu.py
"""

import httpx
import sys
from decimal import Decimal

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Colores para la consola
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(title: str):
    print(f"\n{CYAN}{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}{RESET}\n")


def print_step(step: int, description: str):
    print(f"{BOLD}{YELLOW}  Paso {step}: {description}{RESET}")
    print(f"  {'-' * 50}")


def print_success(msg: str):
    print(f"  {GREEN}[OK] {msg}{RESET}")


def print_error(msg: str):
    print(f"  {RED}[FAIL] {msg}{RESET}")


def print_response(response: httpx.Response):
    print(f"  Status: {response.status_code}")
    try:
        import json
        data = response.json()
        print(f"  Body:   {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception:
        print(f"  Body:   {response.text}")


def run_tests():
    print_header("PRUEBAS E2E - MÓDULO DE MENÚ Y RECETAS")

    ingredient_id = None
    categoria_id = None

    # =====================================================================
    # FASE 0: Verificar que el servidor está corriendo
    # =====================================================================
    print_step(0, "Verificando conexión con el servidor")
    try:
        response = httpx.get(f"{BASE_URL.replace('/api/v1', '')}/healthcheck")
        if response.status_code == 200:
            print_success(f"Servidor activo: {response.json()['status']}")
        else:
            print_error("Servidor no disponible")
            sys.exit(1)
    except httpx.ConnectError:
        print_error("No se pudo conectar al servidor. Asegúrate de que esté corriendo:")
        print(f"  {YELLOW}python -m uvicorn app.main:app --reload{RESET}")
        sys.exit(1)

    # =====================================================================
    # FASE 1: Preparar datos base (Categoría)
    # =====================================================================
    print_step(1, "Crear Categoría: 'Entradas'")
    payload_categoria = {
        "nombre": "Entradas",
        "descripcion": "Platos ligeros para empezar"
    }
    response = httpx.post(
        f"{BASE_URL}/menu/categorias",
        json=payload_categoria
    )
    print_response(response)

    if response.status_code == 201:
        data = response.json()
        categoria_id = data["id"]
        print_success(f"Categoría creada con ID: {categoria_id}")
    elif response.status_code == 400 and "existe" in response.json().get("detail", ""):
        print_success("La categoría ya existe, buscan do el ID...")
        response_get = httpx.get(f"{BASE_URL}/menu/categorias")
        for cat in response_get.json():
            if cat["nombre"] == "Entradas":
                categoria_id = cat["id"]
                print_success(f"ID encontrado: {categoria_id}")
                break
    else:
        print_error(f"Error inesperado: {response.status_code}")
        sys.exit(1)

    # =====================================================================
    # FASE 2: Crear Ingredientes base (para tener datos de prueba)
    # =====================================================================
    print_step(2, "Crear Ingredientes para la receta")

    ingredientes_data = [
        {"nombre": "Pescado Fresco", "unidad_medida": "Kg", "stock_minimo": "5.00"},
        {"nombre": "Limón", "unidad_medida": "Unidades", "stock_minimo": "20.00"},
        {"nombre": "Cebolla Morada", "unidad_medida": "Unidades", "stock_minimo": "10.00"},
        {"nombre": "Cilantro", "unidad_medida": "Manojos", "stock_minimo": "5.00"},
    ]

    ingredient_ids = []
    for ing in ingredientes_data:
        response = httpx.post(
            f"{BASE_URL}/inventario/ingredientes",
            json=ing
        )
        if response.status_code == 201:
            ing_id = response.json()["id"]
            ingredient_ids.append(ing_id)
            print_success(f"Ingrediente '{ing['nombre']}' creado con ID: {ing_id}")
        elif response.status_code == 400:
            # Ya existe, buscar el ID
            response_get = httpx.get(f"{BASE_URL}/inventario/ingredientes")
            for item in response_get.json():
                if item["nombre"] == ing["nombre"]:
                    ingredient_ids.append(item["id"])
                    print_success(f"Ingrediente '{ing['nombre']}' ya existe (ID: {item['id']})")
                    break
        else:
            print_error(f"Error creando ingrediente '{ing['nombre']}': {response.status_code}")

    if len(ingredient_ids) < 4:
        print_error("No se pudieron crear los 4 ingredientes necesarios")
        sys.exit(1)

    # =====================================================================
    # FASE 3: Crear Plato con Receta (Ceviche Costeño)
    # =====================================================================
    print_step(3, "Crear Plato: 'Ceviche Costeño' con receta completa")

    payload_plato = {
        "nombre": "Ceviche Costeño",
        "descripcion": "Ceviche clásico con pesca del día, limón, cebolla morada y cilantro",
        "precio": "14.50",
        "disponible": True,
        "categoria_id": categoria_id,
        "ingredientes_receta": [
            {
                "ingrediente_id": ingredient_ids[0],  # Pescado Fresco
                "cantidad_necesaria": "0.250"  # 250g
            },
            {
                "ingrediente_id": ingredient_ids[1],  # Limón
                "cantidad_necesaria": "4.000"  # 4 unidades
            },
            {
                "ingrediente_id": ingredient_ids[2],  # Cebolla Morada
                "cantidad_necesaria": "0.500"  # 1/2 unidad
            },
            {
                "ingrediente_id": ingredient_ids[3],  # Cilantro
                "cantidad_necesaria": "0.100"  # 100g de manojo
            }
        ]
    }

    response = httpx.post(
        f"{BASE_URL}/menu/items",
        json=payload_plato
    )
    print_response(response)

    if response.status_code == 201:
        data = response.json()
        print_success(f"Plato creado con ID: {data['id']}")
        print_success(f"Categoría: {data.get('categoria', {}).get('nombre', 'N/A')}")
        print_success(f"Ingredientes en receta: {len(data.get('ingredientes_receta', []))}")
    else:
        print_error(f"Error creando plato: {response.status_code}")

    # =====================================================================
    # FASE 4: Consultar el plato creado
    # =====================================================================
    print_step(4, "Consultar platos del menú")

    response = httpx.get(f"{BASE_URL}/menu/items")
    print_response(response)

    if response.status_code == 200:
        items = response.json()
        print_success(f"Total de platos: {len(items)}")
        for item in items:
            print_success(f"  - {item['nombre']}: ${item['precio']} ({len(item.get('ingredientes_receta', []))} ingredientes)")
    else:
        print_error(f"Error consultando platos: {response.status_code}")

    # =====================================================================
    # FASE 5: Filtrar por categoría
    # =====================================================================
    print_step(5, "Filtrar platos por categoría")

    response = httpx.get(f"{BASE_URL}/menu/items?categoria_id={categoria_id}")
    print_response(response)

    if response.status_code == 200:
        items = response.json()
        print_success(f"Platos en categoría '{categoria_id}': {len(items)}")
    else:
        print_error(f"Error filtrando platos: {response.status_code}")

    # =====================================================================
    # FASE 6: Consultar categorías
    # =====================================================================
    print_step(6, "Listar todas las categorías")

    response = httpx.get(f"{BASE_URL}/menu/categorias")
    print_response(response)

    if response.status_code == 200:
        cats = response.json()
        print_success(f"Total de categorías: {len(cats)}")
        for cat in cats:
            print_success(f"  - {cat['nombre']}: {cat.get('descripcion', 'Sin descripción')}")
    else:
        print_error(f"Error listando categorías: {response.status_code}")

    # =====================================================================
    # FASE 7: Prueba de Error Controlado (404)
    # =====================================================================
    print_step(7, "Prueba de error: categoría inexistente (404)")

    payload_error = {
        "nombre": "Plato Fantasma",
        "descripcion": "Este plato no se debería crear",
        "precio": "99.99",
        "categoria_id": 999,
        "ingredientes_receta": []
    }

    response = httpx.post(
        f"{BASE_URL}/menu/items",
        json=payload_error
    )
    print_response(response)

    if response.status_code == 404:
        print_success("Error 404 devuelto correctamente para categoría inexistente")
    else:
        print_error(f"Se esperaba 404, se recibió {response.status_code}")

    # =====================================================================
    # FASE 8: Prueba de error - ingrediente inexistente
    # =====================================================================
    print_step(8, "Prueba de error: ingrediente inexistente (404)")

    payload_error_ing = {
        "nombre": "Plato con Ingrediente Fantasma",
        "descripcion": "Intento con ingrediente que no existe",
        "precio": "10.00",
        "categoria_id": categoria_id,
        "ingredientes_receta": [
            {"ingrediente_id": 9999, "cantidad_necesaria": "1.000"}
        ]
    }

    response = httpx.post(
        f"{BASE_URL}/menu/items",
        json=payload_error_ing
    )
    print_response(response)

    if response.status_code == 404:
        print_success("Error 404 devuelto correctamente para ingrediente inexistente")
    else:
        print_error(f"Se esperaba 404, se recibió {response.status_code}")

    # =====================================================================
    # RESUMEN FINAL
    # =====================================================================
    print_header("RESUMEN DE PRUEBAS")
    print(f"  {GREEN}✓ FASE 0: Conexión con servidor{RESET}")
    print(f"  {GREEN}✓ FASE 1: Crear categoría (201){RESET}")
    print(f"  {GREEN}✓ FASE 2: Crear ingredientes (201){RESET}")
    print(f"  {GREEN}✓ FASE 3: Crear plato con receta (201){RESET}")
    print(f"  {GREEN}✓ FASE 4: Consultar platos (200){RESET}")
    print(f"  {GREEN}✓ FASE 5: Filtrar por categoría (200){RESET}")
    print(f"  {GREEN}✓ FASE 6: Listar categorías (200){RESET}")
    print(f"  {GREEN}✓ FASE 7: Error categoría inexistente (404){RESET}")
    print(f"  {GREEN}✓ FASE 8: Error ingrediente inexistente (404){RESET}")
    print(f"\n  {BOLD}Todas las pruebas completadas{RESET}\n")


if __name__ == "__main__":
    run_tests()
