"""
Script de pruebas E2E para el módulo de Órdenes y Facturación.
Ejecutar con el servidor corriendo: python -m uvicorn app.main:app --reload

Uso: python tests/test_ordenes.py
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

    print_header("PRUEBAS E2E — MÓDULO DE ÓRDENES Y FACTURACIÓN")

    orden_id = None
    total_esperado = None

    # =================================================================
    # FASE 0: Verificar conexión con el servidor
    # =================================================================
    print_step(0, "Verificar conexión con el servidor")
    try:
        r = httpx.get(f"{BASE_URL.replace('/api/v1', '')}/healthcheck", timeout=5)
        check(
            r.status_code == 200,
            f"Servidor respondió 200 (status={r.status_code})",
            f"Se esperaba 200, se obtuvo {r.status_code}"
        )
    except httpx.ConnectError:
        print(f"    {RED}[✗] No se pudo conectar al servidor en {BASE_URL}{RESET}")
        print(f"\n    {YELLOW}Inicia el servidor con:{RESET}")
        print(f"    python -m uvicorn app.main:app --reload\n")
        sys.exit(1)

    # =================================================================
    # FASE 0.5: Setup - Crear empleado + usuario mesero
    # =================================================================
    print_step(0.5, "Setup: crear empleado y usuario mesero ( FK para mesero_id )")

    # Crear empleado (ignora 400 si ya existe)
    r_emp = httpx.post(f"{BASE_URL}/personal/empleados", json={
        "cedula": "TEST-ORD-001",
        "nombre": "Mesero Test",
        "apellido": "Ordenes",
        "telefono": "3000000000",
        "puesto_id": 1,
        "salario_base": 1200000.00,
        "fecha_ingreso": "2025-01-01"
    }, timeout=10, follow_redirects=True)

    if r_emp.status_code in (201, 400):
        # Buscar empleado por cedula
        r_list = httpx.get(f"{BASE_URL}/personal/empleados?cedula=TEST-ORD-001", timeout=10)
        if r_list.status_code == 200 and r_list.json():
            empleado_id = r_list.json()[0]["id"]
        else:
            empleado_id = 1
        check(True, f"Empleado mesero disponible (id={empleado_id})", "")
    else:
        empleado_id = 1
        check(True, f"Usando empleado existente (id={empleado_id})", "")

    # Crear usuario para el mesero (ignora 400 si ya existe)
    r_usr = httpx.post(f"{BASE_URL}/personal/usuarios", json={
        "username": "mesero_ord_test",
        "password": "test1234",
        "empleado_id": empleado_id,
        "rol": "Vendedor"
    }, timeout=10, follow_redirects=True)

    if r_usr.status_code in (201, 400):
        # Obtener ID del usuario
        r_usr_list = httpx.get(f"{BASE_URL}/personal/usuarios", timeout=10)
        mesero_id = None
        if r_usr_list.status_code == 200:
            for u in r_usr_list.json():
                if u.get("username") == "mesero_ord_test":
                    mesero_id = u["id"]
                    break
        if mesero_id is None:
            mesero_id = 1
        check(True, f"Usuario mesero disponible (id={mesero_id})", "")
    else:
        mesero_id = 1
        check(True, f"Usando usuario existente (id={mesero_id})", "")

    # =================================================================
    # FASE 1: Crear una Orden en Mesa 1
    # =================================================================
    print_step(1, "Crear una Orden en Mesa 1 (3x Ceviche Costeño ID=1)")
    payload = {
        "mesa_id": 1,
        "detalles": [
            {"producto_id": 1, "cantidad": 3, "notas": "Sin picante"},
        ]
    }
    r = httpx.post(
        f"{BASE_URL}/ordenes/?mesero_id={mesero_id}",
        json=payload,
        timeout=10,
        follow_redirects=True
    )
    check(
        r.status_code == 201,
        f"Orden creada exitosamente (status={r.status_code})",
        f"Se esperaba 201, se obtuvo {r.status_code}: {r.text[:200]}"
    )
    if r.status_code == 201:
        data = r.json()
        orden_id = data.get("id")
        check(
            orden_id is not None,
            f"Orden tiene ID: {orden_id}",
            "La respuesta no contiene campo 'id'"
        )

    # =================================================================
    # FASE 2: Validar la respuesta de la orden
    # =================================================================
    print_step(2, "Validar respuesta: total calculado y estado PENDIENTE")
    if r.status_code == 201:
        data = r.json()
        check(
            data.get("estado") == "PENDIENTE",
            f"Estado es 'PENDIENTE': {data.get('estado')}",
            f"Se esperaba 'PENDIENTE', se obtuvo '{data.get('estado')}'"
        )

        total_api = data.get("total")
        if total_api is not None:
            total_api_decimal = Decimal(str(total_api))
            total_esperado = total_api_decimal

            check(
                total_api_decimal > 0,
                f"Total calculado correctamente: {total_api_decimal}",
                f"Total debe ser > 0, se obtuvo: {total_api_decimal}"
            )

            detalles = data.get("detalles", [])
            check(
                len(detalles) == 1,
                f"La orden tiene 1 detalle (obtuvo {len(detalles)})",
                f"Se esperaba 1 detalle, se obtuvieron {len(detalles)}"
            )

            for d in detalles:
                check(
                    "precio_unitario" in d and Decimal(str(d["precio_unitario"])) > 0,
                    f"Detalle #{d.get('id')} tiene precio_unitario: {d.get('precio_unitario')}",
                    f"Detalle #{d.get('id')} no tiene precio_unitario válido"
                )
        else:
            check(False, "", "No se pudo obtener el campo 'total' de la respuesta")

    # =================================================================
    # FASE 3: Filtrar por estado=PENDIENTE
    # =================================================================
    print_step(3, "Consultar órdenes con filtro ?estado=PENDIENTE")
    r = httpx.get(f"{BASE_URL}/ordenes/?estado=PENDIENTE", timeout=10, follow_redirects=True)
    check(
        r.status_code == 200,
        f"Consulta exitosa (status={r.status_code})",
        f"Se esperaba 200, se obtuvo {r.status_code}"
    )
    if r.status_code == 200:
        ordenes = r.json()
        ids_encontrados = [o.get("id") for o in ordenes]
        check(
            len(ordenes) > 0,
            f"Se encontraron {len(ordenes)} órdenes con estado PENDIENTE",
            "No se encontraron órdenes PENDIENTE"
        )
        if orden_id:
            check(
                orden_id in ids_encontrados,
                f"La orden {orden_id} aparece en los resultados",
                f"La orden {orden_id} NO aparece (encontrados: {ids_encontrados})"
            )

    # =================================================================
    # FASE 4: Cambiar estado a PREPARANDO
    # =================================================================
    print_step(4, "Cambiar estado a PREPARANDO (PATCH)")
    if orden_id:
        r = httpx.patch(
            f"{BASE_URL}/ordenes/{orden_id}/estado",
            json={"estado": "PREPARANDO"},
            timeout=10,
            follow_redirects=True
        )
        check(
            r.status_code == 200,
            f"Estado actualizado a PREPARANDO (status={r.status_code})",
            f"Se esperaba 200, se obtuvo {r.status_code}: {r.text[:200]}"
        )
        if r.status_code == 200:
            data = r.json()
            check(
                data.get("estado") == "PREPARANDO",
                f"Estado confirmado: {data.get('estado')}",
                f"Se esperaba 'PREPARANDO', se obtuvo '{data.get('estado')}'"
            )

    # =================================================================
    # FASE 5: Cambiar estado a PAGADA (factura cobrada)
    # =================================================================
    print_step(5, "Cambiar estado a PAGADA — Simulación de cobro (PATCH)")
    if orden_id:
        r = httpx.patch(
            f"{BASE_URL}/ordenes/{orden_id}/estado",
            json={"estado": "PAGADA"},
            timeout=10,
            follow_redirects=True
        )
        check(
            r.status_code == 200,
            f"Orden marcada como PAGADA (status={r.status_code})",
            f"Se esperaba 200, se obtuvo {r.status_code}: {r.text[:200]}"
        )
        if r.status_code == 200:
            data = r.json()
            check(
                data.get("estado") == "PAGADA",
                f"Estado final: {data.get('estado')}",
                f"Se esperaba 'PAGADA', se obtuvo '{data.get('estado')}'"
            )

    # =================================================================
    # FASE 6: Orden con producto inexistente (defensivo)
    # =================================================================
    print_step(6, "Defensiva: crear orden con producto_id=999 (inexistente)")
    payload_invalido = {
        "mesa_id": 1,
        "detalles": [
            {"producto_id": 999, "cantidad": 1, "notas": None}
        ]
    }
    r = httpx.post(f"{BASE_URL}/ordenes/?mesero_id={mesero_id}", json=payload_invalido, timeout=10, follow_redirects=True)
    check(
        r.status_code == 404,
        f"Rechazada correctamente (status={r.status_code})",
        f"Se esperaba 404, se obtuvo {r.status_code}"
    )
    if r.status_code == 404:
        error = r.json()
        check(
            "999" in str(error.get("detail", "")),
            f"Mensaje claro: '{error.get('detail', '')}'",
            f"El mensaje no menciona el ID 999: {error}"
        )

    # =================================================================
    # RESUMEN FINAL
    # =================================================================
    total = passed + failed
    print(f"\n{CYAN}{'=' * 65}")
    print(f"  RESUMEN DE PRUEBAS")
    print(f"{'=' * 65}{RESET}")
    print(f"  {GREEN}Pasaron: {passed}{RESET}")
    if failed:
        print(f"  {RED}Fallaron: {failed}{RESET}")
    print(f"  Total:   {total}")
    print(f"{CYAN}{'=' * 65}{RESET}\n")

    if total_esperado:
        print(f"  {BOLD}Detalle financiero:{RESET}")
        print(f"    Total de la orden: {total_esperado}")
        print(f"    Estado final:      PAGADA")
        print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run_tests()
