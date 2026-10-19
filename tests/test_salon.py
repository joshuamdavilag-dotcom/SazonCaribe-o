"""
Script de pruebas E2E para el módulo de Salón y Mesas.
Ejecutar con el servidor corriendo: python -m uvicorn app.main:app --reload

Uso: python tests/test_salon.py
"""

import httpx
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Colores para la consola
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0


def print_header(title: str):
    print(f"\n{CYAN}{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}{RESET}\n")


def print_step(step: int, description: str):
    print(f"\n{BOLD}{YELLOW}  PASO {step}: {description}")
    print(f"  {'-' * 55}{RESET}")


def check(condition: bool, msg_ok: str, msg_fail: str):
    global passed, failed
    if condition:
        print(f"    {GREEN}[✓] {msg_ok}{RESET}")
        passed += 1
    else:
        print(f"    {RED}[✗] {msg_fail}{RESET}")
        failed += 1


def run_tests():
    global passed, failed

    print_header("PRUEBAS E2E — MÓDULO DE SALÓN Y MESAS")

    zona_terrazza_id = None
    zona_salon_id = None
    mesa_terrazza_1_id = None

    # =================================================================
    # FASE 0: Conexión con el servidor
    # =================================================================
    print_step(0, "Verificar conexión con el servidor")
    try:
        r = httpx.get(f"{BASE_URL.replace('/api/v1', '')}/healthcheck")
        check(
            r.status_code == 200,
            f"Servidor activo ({r.json()['status']})",
            f"Servidor no disponible (status {r.status_code})"
        )
    except httpx.ConnectError:
        print(f"\n  {RED}No se pudo conectar al servidor.{RESET}")
        print(f"  Ejecuta: {YELLOW}python -m uvicorn app.main:app --reload{RESET}\n")
        sys.exit(1)

    # =================================================================
    # FASE 1: Crear Zona "Terraza"
    # =================================================================
    print_step(1, 'Crear Zona "Terraza"')
    r = httpx.post(f"{BASE_URL}/salon/zonas", json={
        "nombre": "Terraza",
        "descripcion": "Área al aire libre con vista al mar"
    })
    check(
        r.status_code == 201,
        f"Status 201 — Zona creada: {r.json().get('nombre')}",
        f"Se esperaba 201, se recibió {r.status_code}"
    )
    if r.status_code == 201:
        zona_terrazza_id = r.json()["id"]
        check(True, f"ID asignado: {zona_terrazza_id}", "")

    # =================================================================
    # FASE 2: Crear Zona "Salón Principal"
    # =================================================================
    print_step(2, 'Crear Zona "Salón Principal"')
    r = httpx.post(f"{BASE_URL}/salon/zonas", json={
        "nombre": "Salón Principal",
        "descripcion": "Área principal del restaurante con aire acondicionado"
    })
    check(
        r.status_code == 201,
        f"Status 201 — Zona creada: {r.json().get('nombre')}",
        f"Se esperaba 201, se recibió {r.status_code}"
    )
    if r.status_code == 201:
        zona_salon_id = r.json()["id"]
        check(True, f"ID asignado: {zona_salon_id}", "")

    # =================================================================
    # FASE 3: Crear Mesa 1 en Terraza (capacidad 4)
    # =================================================================
    print_step(3, "Crear Mesa 1 en Terraza (capacidad 4)")
    r = httpx.post(f"{BASE_URL}/salon/mesas", json={
        "numero": 1,
        "capacidad": 4,
        "zona_id": zona_terrazza_id
    })
    check(
        r.status_code == 201,
        f"Status 201 — Mesa {r.json().get('numero')} creada (ID: {r.json().get('id')})",
        f"Se esperaba 201, se recibió {r.status_code}"
    )
    if r.status_code == 201:
        mesa_terrazza_1_id = r.json()["id"]
        check(
            r.json().get("estado") == "LIBRE",
            f"Estado inicial: {r.json().get('estado')}",
            f"Estado inesperado: {r.json().get('estado')}"
        )

    # =================================================================
    # FASE 4: Crear Mesa 2 en Terraza (capacidad 2)
    # =================================================================
    print_step(4, "Crear Mesa 2 en Terraza (capacidad 2)")
    r = httpx.post(f"{BASE_URL}/salon/mesas", json={
        "numero": 2,
        "capacidad": 2,
        "zona_id": zona_terrazza_id
    })
    check(
        r.status_code == 201,
        f"Status 201 — Mesa {r.json().get('numero')} creada (capacidad: {r.json().get('capacidad')})",
        f"Se esperaba 201, se recibió {r.status_code}"
    )

    # =================================================================
    # FASE 5: Crear Mesa 1 en Salón Principal (capacidad 6)
    # =================================================================
    print_step(5, "Crear Mesa 1 en Salón Principal (capacidad 6) — Independencia de zona")
    r = httpx.post(f"{BASE_URL}/salon/mesas", json={
        "numero": 1,
        "capacidad": 6,
        "zona_id": zona_salon_id
    })
    check(
        r.status_code == 201,
        f"Status 201 — Mesa 1 creada en Salón (independiente de Terraza)",
        f"Se esperaba 201, se recibió {r.status_code}"
    )
    check(
        r.status_code == 201 and r.json().get("zona_id") == zona_salon_id,
        f"zona_id correcto: {r.json().get('zona_id')} (Salón Principal)",
        f"zona_id incorrecto"
    )

    # =================================================================
    # FASE 6: Duplicado defensivo — Mesa 1 en Terraza otra vez
    # =================================================================
    print_step(6, 'Intentar crear Mesa 1 en Terraza otra vez (espera 400)')
    r = httpx.post(f"{BASE_URL}/salon/mesas", json={
        "numero": 1,
        "capacidad": 4,
        "zona_id": zona_terrazza_id
    })
    check(
        r.status_code == 400,
        f"Status 400 — Duplicado rechazado: {r.json().get('detail')}",
        f"Se esperaba 400, se recibió {r.status_code}"
    )

    # =================================================================
    # FASE 7: Consultar mapa completo del restaurante
    # =================================================================
    print_step(7, "Consultar GET /salon/mapa — Validar estructura")
    r = httpx.get(f"{BASE_URL}/salon/mapa")
    check(
        r.status_code == 200,
        f"Status 200 — Mapa obtenido",
        f"Se esperaba 200, se recibió {r.status_code}"
    )

    zonas = r.json()
    check(
        isinstance(zonas, list) and len(zonas) >= 2,
        f"Se encontraron {len(zonas)} zonas",
        f"Se esperaban al menos 2 zonas, se encontraron {len(zonas)}"
    )

    for zona in zonas:
        mesas = zona.get("mesas", [])
        print(f"    {CYAN}  Zona: {zona['nombre']} ({len(mesas)} mesas){RESET}")
        for mesa in mesas:
            print(
                f"      → Mesa {mesa['numero']} | "
                f"Cap: {mesa['capacidad']} | "
                f"Estado: {mesa['estado']}"
            )

    # Validar que Terraza tiene 2 mesas
    terraza = next((z for z in zonas if z["nombre"] == "Terraza"), None)
    check(
        terraza is not None and len(terraza.get("mesas", [])) == 2,
        "Terraza tiene 2 mesas",
        f"Terraza debería tener 2 mesas, tiene {len(terraza.get('mesas', [])) if terraza else 0}"
    )

    # Validar que Salón Principal tiene 1 mesa
    salon = next((z for z in zonas if z["nombre"] == "Salón Principal"), None)
    check(
        salon is not None and len(salon.get("mesas", [])) == 1,
        "Salón Principal tiene 1 mesa",
        f"Salón Principal debería tener 1 mesa, tiene {len(salon.get('mesas', [])) if salon else 0}"
    )

    # =================================================================
    # FASE 8: Cambiar estado de Mesa 1 Terraza a OCUPADA
    # =================================================================
    print_step(8, "PATCH /salon/mesas/{id}/estado → Cambiar a OCUPADA")
    r = httpx.patch(
        f"{BASE_URL}/salon/mesas/{mesa_terrazza_1_id}/estado",
        json={"nuevo_estado": "OCUPADA"}
    )
    check(
        r.status_code == 200,
        f"Status 200 — Estado actualizado",
        f"Se esperaba 200, se recibió {r.status_code}"
    )
    check(
        r.status_code == 200 and r.json().get("estado") == "OCUPADA",
        f"Nuevo estado: {r.json().get('estado')}",
        f"Estado inesperado: {r.json().get('estado')}"
    )

    # =================================================================
    # VERIFICACIÓN EXTRA: Confirmar cambio en el mapa
    # =================================================================
    print_step(8.1, "Verificar cambio en el mapa completo")
    r = httpx.get(f"{BASE_URL}/salon/mapa")
    terraza = next((z for z in r.json() if z["nombre"] == "Terraza"), None)
    mesa_1 = next((m for m in terraza["mesas"] if m["numero"] == 1), None) if terraza else None
    check(
        mesa_1 is not None and mesa_1["estado"] == "OCUPADA",
        f"Mesa 1 en Terraza ahora está OCUPADA",
        f"Mesa 1 debería ser OCUPADA, es {mesa_1.get('estado') if mesa_1 else 'N/A'}"
    )

    # =================================================================
    # RESUMEN FINAL
    # =================================================================
    print_header("REPORTE DE PRUEBAS")
    total = passed + failed
    print(f"  Total: {total}  |  {GREEN}Pasaron: {passed}{RESET}  |  {RED}Fallaron: {failed}{RESET}")
    print()
    if failed == 0:
        print(f"  {GREEN}{BOLD}✓ TODAS LAS PRUEBAS PASARON CORRECTAMENTE{RESET}")
    else:
        print(f"  {RED}{BOLD}✗ HAY PRUEBAS FALLIDAS{RESET}")
    print()


if __name__ == "__main__":
    run_tests()
