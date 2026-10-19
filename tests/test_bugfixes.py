"""
E2E tests for Bug fixes: stock deduction, employee edit, cancellation reversion.
Run with server: python -m uvicorn app.main:app --reload

Usage: python tests/test_bugfixes.py
"""

import httpx
import sys
from decimal import Decimal

BASE_URL = "http://127.0.0.1:8000/api/v1"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0


def check(condition, msg_ok, msg_fail=""):
    global passed, failed
    if condition:
        print(f"    {GREEN}[✓] {msg_ok}{RESET}")
        passed += 1
    else:
        print(f"    {RED}[✗] {msg_fail or msg_ok}{RESET}")
        failed += 1


def login_admin():
    r = httpx.post(f"{BASE_URL.replace('/api/v1', '')}/api/v1/auth/login",
                   json={"username": "admin", "password": "password123"}, timeout=10)
    if r.status_code != 200:
        print(f"    {RED}Login failed: {r.status_code} {r.text[:200]}{RESET}")
        sys.exit(1)
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def get_ingrediente_stock(h, ingrediente_id=1):
    r = httpx.get(f"{BASE_URL}/inventario/ingredientes", headers=h, timeout=10)
    for ing in r.json():
        if ing["id"] == ingrediente_id:
            return Decimal(str(ing["stock_actual"]))
    return None


def run_tests():
    global passed, failed

    print(f"\n{CYAN}{'=' * 65}")
    print(f"  E2E TESTS — Bug Fixes Verification")
    print(f"{'=' * 65}{RESET}\n")

    # =================================================================
    # PHASE 0: Server check + login
    # =================================================================
    print(f"{BOLD}{YELLOW}  Phase 0: Setup{RESET}")
    print(f"  {'-' * 50}")

    try:
        r = httpx.get(f"{BASE_URL.replace('/api/v1', '')}/healthcheck", timeout=5)
        check(r.status_code == 200, "Server alive", f"Status: {r.status_code}")
    except httpx.ConnectError:
        print(f"    {RED}Server not running at {BASE_URL}{RESET}")
        print(f"    Start with: python -m uvicorn app.main:app --reload")
        sys.exit(1)

    token = login_admin()
    h = auth_headers(token)
    check(True, "Admin login successful")

    # =================================================================
    # PHASE 1: Stock deduction on order creation
    # =================================================================
    print(f"\n{BOLD}{YELLOW}  Phase 1: Stock deduction on order creation{RESET}")
    print(f"  {'-' * 50}")

    # Read current stock of Camarón (id=1) and Pescado Fresco (id=13)
    camarón_before = get_ingrediente_stock(h, 1)
    pescado_before = get_ingrediente_stock(h, 13)
    check(camarón_before is not None, f"Camarón initial stock: {camarón_before}")
    check(pescado_before is not None, f"Pescado Fresco initial stock: {pescado_before}")

    # Find a free mesa
    r = httpx.get(f"{BASE_URL}/salon/mapa", headers=h, timeout=10)
    mesa_libre = None
    if r.status_code == 200:
        for zona in r.json():
            for m in zona.get("mesas", []):
                if m.get("estado") == "LIBRE":
                    mesa_libre = m["numero"]
                    break
            if mesa_libre:
                break
    check(mesa_libre is not None, f"Found free mesa: #{mesa_libre}", f"No free mesas available")
    if not mesa_libre:
        # Use PATCH to free a mesa
        r = httpx.patch(f"{BASE_URL}/salon/mesas/1/estado", headers=h, json={"estado": "LIBRE"}, timeout=10)
        if r.status_code == 200:
            mesa_libre = 1
            print(f"    {YELLOW}Freed mesa 1 via PATCH{RESET}")
        else:
            print(f"    {RED}Cannot free mesas, aborting{RESET}")
            sys.exit(1)

    # Create order: 2x Mariscada del Caribe (id=1)
    # Recipe: 0.500 Camarón + 0.300 Pescado Fresco per unit
    # 2 units → deduct 1.000 Camarón + 0.600 Pescado
    payload = {
        "mesa_id": mesa_libre,
        "detalles": [
            {"producto_id": 1, "cantidad": 2}
        ]
    }
    r = httpx.post(f"{BASE_URL}/ordenes/", headers=h, json=payload, timeout=10)
    check(r.status_code == 201, f"Order created → {r.status_code}", f"Expected 201, got {r.status_code}: {r.text[:200]}")

    orden_id = None
    camarón_after = camarón_before
    if r.status_code == 201:
        orden = r.json()
        orden_id = orden["id"]
        check(orden["estado"] == "PENDIENTE", f"Estado = PENDIENTE")

        camarón_after = get_ingrediente_stock(h, 1)
        pescado_after = get_ingrediente_stock(h, 13)
        deduction_camarón = camarón_before - camarón_after
        deduction_pescado = pescado_before - pescado_after

        check(
            deduction_camarón == Decimal("1.000"),
            f"Camarón deducted: {deduction_camarón} (expected 1.000)",
            f"Camarón deduction wrong: got {deduction_camarón}, expected 1.000"
        )
        check(
            deduction_pescado == Decimal("0.600"),
            f"Pescado deducted: {deduction_pescado} (expected 0.600)",
            f"Pescado deduction wrong: got {deduction_pescado}, expected 0.600"
        )
    else:
        check(False, "", "Cannot continue without order creation")

    # =================================================================
    # PHASE 2: Stock reversion on cancellation
    # =================================================================
    print(f"\n{BOLD}{YELLOW}  Phase 2: Stock reversion on cancel{RESET}")
    print(f"  {'-' * 50}")

    if orden_id:
        camarón_before_cancel = get_ingrediente_stock(h, 1)
        pescado_before_cancel = get_ingrediente_stock(h, 13)

        # Cancel the order
        r = httpx.patch(
            f"{BASE_URL}/ordenes/{orden_id}/estado",
            headers=h,
            json={"estado": "CANCELADA"},
            timeout=10
        )
        check(r.status_code == 200, f"Order cancelled → {r.status_code}", f"Expected 200, got {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            check(r.json().get("estado") == "CANCELADA", f"Estado = CANCELADA")

        camarón_restored = get_ingrediente_stock(h, 1) - camarón_before_cancel
        pescado_restored = get_ingrediente_stock(h, 13) - pescado_before_cancel

        check(
            camarón_restored == Decimal("1.000"),
            f"Camarón restored: +{camarón_restored} (expected +1.000)",
            f"Camarón NOT restored: +{camarón_restored}"
        )
        check(
            pescado_restored == Decimal("0.600"),
            f"Pescado restored: +{pescado_restored} (expected +0.600)",
            f"Pescado NOT restored: +{pescado_restored}"
        )
    else:
        check(False, "", "Skipped — no order to cancel")

    # =================================================================
    # PHASE 3: Employee salary_base not overridden on create
    # =================================================================
    print(f"\n{BOLD}{YELLOW}  Phase 3: Employee salario_base preserved on create{RESET}")
    print(f"  {'-' * 50}")

    custom_salary = Decimal("8888.88")
    ts = int(__import__('time').time()) % 100000
    unique_ced = f"BUG-SAL-{ts}"
    r = httpx.post(f"{BASE_URL}/personal/empleados", headers=h, json={
        "nombre": "Test",
        "apellido": "SalaryBug",
        "cedula_identidad": unique_ced,
        "telefono": "88889999",
        "puesto_id": 3,
        "salario_base": float(custom_salary),
    }, timeout=10)

    emp_id = None
    if r.status_code == 201:
        emp = r.json()
        emp_id = emp["id"]
        actual_salary = Decimal(str(emp["salario_base"]))
        check(
            actual_salary == custom_salary,
            f"Salary preserved on create: {actual_salary} (expected {custom_salary})",
            f"Salary overridden: got {actual_salary}, expected {custom_salary}"
        )
        check(
            emp.get("telefono") == "88889999",
            f"Phone saved: {emp.get('telefono')}",
            f"Phone not saved: {emp.get('telefono')}"
        )
    else:
        check(False, "", f"Create employee failed: {r.status_code}: {r.text[:200]}")

    # =================================================================
    # PHASE 4: Employee salary_base editable via PUT
    # =================================================================
    print(f"\n{BOLD}{YELLOW}  Phase 4: Employee salary_base editable via PUT{RESET}")
    print(f"  {'-' * 50}")

    if emp_id:
        new_salary = Decimal("9999.99")
        r = httpx.put(f"{BASE_URL}/personal/empleados/{emp_id}", headers=h, json={
            "salario_base": float(new_salary),
            "telefono": "77776666",
        }, timeout=10)
        check(r.status_code == 200, f"PUT /empleados/{emp_id} → {r.status_code}", f"Expected 200, got {r.status_code}: {r.text[:200]}")

        if r.status_code == 200:
            updated = r.json()
            actual = Decimal(str(updated["salario_base"]))
            check(
                actual == new_salary,
                f"Salary updated: {actual} (expected {new_salary})",
                f"Salary not updated: got {actual}, expected {new_salary}"
            )
            check(
                updated.get("telefono") == "77776666",
                f"Phone updated: {updated.get('telefono')}",
                f"Phone not updated: {updated.get('telefono')}"
            )
    else:
        check(False, "", "Skipped — no employee to edit")

    # =================================================================
    # PHASE 5: Order rejected when stock is insufficient
    # =================================================================
    print(f"\n{BOLD}{YELLOW}  Phase 5: Order rejected with insufficient stock{RESET}")
    print(f"  {'-' * 50}")

    payload_fail = {
        "mesa_id": 5,
        "detalles": [
            {"producto_id": 1, "cantidad": 100}
        ]
    }
    r = httpx.post(f"{BASE_URL}/ordenes/", headers=h, json=payload_fail, timeout=10)
    check(
        r.status_code == 400,
        f"Order rejected (insufficient stock) → {r.status_code}",
        f"Expected 400, got {r.status_code}"
    )
    if r.status_code == 400:
        error = r.json()
        check(
            "stock" in error.get("detail", "").lower() or "suficiente" in error.get("detail", "").lower(),
            f"Error mentions stock: {error.get('detail', '')}",
            f"Unexpected error: {error.get('detail', '')}"
        )

    # Verify stock unchanged after failed order
    stock_after_fail = get_ingrediente_stock(h, 1)
    check(
        stock_after_fail == camarón_before,
        f"Camarón stock unchanged after failed order: {stock_after_fail}",
        f"Stock changed: expected {camarón_before}, got {stock_after_fail}"
    )

    # =================================================================
    # CLEANUP
    # =================================================================
    if emp_id:
        httpx.put(f"{BASE_URL}/personal/empleados/{emp_id}", headers=h,
                   json={"activo": False}, timeout=10)

    # =================================================================
    # SUMMARY
    # =================================================================
    total = passed + failed
    print(f"\n{CYAN}{'=' * 65}")
    print(f"  TEST RESULTS")
    print(f"{'=' * 65}{RESET}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    if failed:
        print(f"  {RED}Failed: {failed}{RESET}")
    print(f"  Total:  {total}")
    print(f"{'=' * 65}{RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run_tests()
