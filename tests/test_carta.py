"""
Script de pruebas E2E para la Carta Digital y los nuevos campos de MenuItem.

Cubre:
- Creación de plato con tiempo_preparacion (imagen_url lo asigna solo el servidor).
- Serialización pública: /api/public/menu e /api/public/item/{id} incluyen
  imagen_url y tiempo_preparacion.
- Subida de imagen por archivo (multipart) → ruta generada por el servidor.
- Reemplazo de imagen → se elimina el archivo anterior de forma segura.
- Validaciones: tipo no permitido (400) y tamaño máximo de 5 MB (400).
- Placeholder: un plato sin imagen NO expone imagen_url remota (null).

Ejecutar con el servidor corriendo: python -m uvicorn app.main:app --reload
Uso: python tests/test_carta.py
"""

import base64
import os
import sys

import httpx

API_V1 = "http://127.0.0.1:8000/api/v1"
API_PUBLIC = "http://127.0.0.1:8000/api/public"
UPLOAD_DIR = os.path.join("app", "Templates", "carta", "img", "platos")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# PNG 1x1 valido
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
# JPEG 1x1 valido
JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
    "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBE"
    "AQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjLy/+AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEB"
    "AAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUS"
    "ITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5"
    "OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeY"
    "mZqio6SkpqanqKmqsrO0tba3uLm6w8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq"
    "8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALUR"
    "AAIBAgQEAwQEBQQEAAECEQABAwIEBQcIAgMDEQEABIXhE0FxMgmxg5HhQhEjVGLh"
    "YjMUGBoqLSU2NysxR1haS1xdYGZnaGp7CImMlJicnKjQ1Njc4OTpDREVGR0hJSlNV"
    "VldYWVpjZGVmZ2hpanB0dXZ3eHl6goSFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqy"
    "s7S1tre4ubrCw8TFxsfIycrS09TV1tfY2dri4+Tl5ufo6ery8/T19vf4+fr/2gA"
    "wAABAAARAP/aAAwDAQACEQMRAD8A/v8A/wD/2g==AAAAAD/2Q=="
)


def print_header(title):
    print(f"\n{CYAN}{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}{RESET}\n")


def print_step(step, description):
    print(f"{BOLD}{YELLOW}  Paso {step}: {description}{RESET}")
    print(f"  {'-' * 50}")


def print_ok(msg):
    print(f"  {GREEN}[OK] {msg}{RESET}")


def print_err(msg):
    print(f"  {RED}[FAIL] {msg}{RESET}")


def print_info(msg):
    print(f"  {YELLOW}[..] {msg}{RESET}")


def auth_headers(client):
    r = client.post(f"{API_V1}/auth/login", json={
        "username": "admin",
        "password": "password123",
    })
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def obtener_o_crear_categoria(client, headers, nombre):
    r = client.get(f"{API_V1}/menu/categorias", headers=headers)
    for cat in r.json():
        if cat["nombre"].lower() == nombre.lower():
            return cat["id"]
    r = client.post(f"{API_V1}/menu/categorias", json={"nombre": nombre}, headers=headers)
    return r.json()["id"]


def limpiar_archivos_upload(item_id):
    if not os.path.isdir(UPLOAD_DIR):
        return
    for nombre in os.listdir(UPLOAD_DIR):
        if nombre.startswith(f"item_{item_id}_"):
            try:
                os.remove(os.path.join(UPLOAD_DIR, nombre))
            except OSError:
                pass


def run_tests():
    print_header("PRUEBAS E2E - CARTA DIGITAL (imagen_url / tiempo_preparacion)")
    client = httpx.Client(timeout=30)

    # ---- FASE 0: servidor + login ----
    print_step(0, "Verificando servidor y login de administrador")
    try:
        r = client.get("http://127.0.0.1:8000/healthcheck")
        if r.status_code != 200:
            print_err("Servidor no disponible"); sys.exit(1)
    except httpx.ConnectError:
        print_err("No se pudo conectar. Asegúrate de que el servidor esté corriendo.")
        sys.exit(1)

    headers = auth_headers(client)
    if not headers:
        print_err("No se pudo autenticar con admin/password123")
        sys.exit(1)
    print_ok("Login OK (admin)")

    # ---- FASE 1: categoría y plato con tiempo_preparacion (sin imagen) ----
    print_step(1, "Crear plato con tiempo_preparacion y sin imagen")
    cat_id = obtener_o_crear_categoria(client, headers, "Carta Test")
    nombre = "Carta Test Platillo"
    # Evitar duplicados de nombre si el test ya corrió
    existing = client.get(f"{API_V1}/menu/items", headers=headers).json()
    item_id = next((i["id"] for i in existing if i["nombre"] == nombre), None)
    if not item_id:
        r = client.post(f"{API_V1}/menu/items", headers=headers, json={
            "nombre": nombre,
            "descripcion": "Platillo para pruebas de la carta digital",
            "precio": "12.50",
            "disponible": True,
            "categoria_id": cat_id,
            "tiempo_preparacion": 25,
        })
        if r.status_code != 201:
            print_err(f"No se pudo crear el plato: {r.status_code} {r.text}")
            sys.exit(1)
        item_id = r.json()["id"]
        print_ok(f"Plato creado con ID {item_id} y tiempo_preparacion=25")
    else:
        print_info(f"Plato ya existía (ID {item_id}), reutilizando")

    r = client.get(f"{API_V1}/menu/items/{item_id}", headers=headers)
    item = r.json()
    assert item["tiempo_preparacion"] == 25, "tiempo_preparacion no se guardó"
    assert item["imagen_url"] is None, "imagen_url debería ser null sin subida"
    print_ok("Backend admin: tiempo_preparacion=25 e imagen_url=null")

    # ---- FASE 2: API pública serializa los campos nuevos ----
    print_step(2, "API pública expone imagen_url y tiempo_preparacion")
    r = client.get(f"{API_PUBLIC}/item/{item_id}")
    pub = r.json()
    assert pub["tiempo_preparacion"] == 25, "API pública no devuelve tiempo_preparacion"
    assert "imagen_url" in pub and pub["imagen_url"] is None, "API pública sin imagen_url"
    assert "receta" not in pub and "ingredientes_receta" not in pub, "API pública filtra datos internos"
    print_ok(f"GET /api/public/item/{item_id} -> imagen_url=null, tiempo_preparacion=25")

    r = client.get(f"{API_PUBLIC}/menu")
    pubs = [p for p in r.json() if p["id"] == item_id]
    assert pubs, "El plato no aparece en /api/public/menu"
    assert "tiempo_preparacion" in pubs[0] and "imagen_url" in pubs[0]
    print_ok("GET /api/public/menu incluye ambos campos")

    # ---- FASE 3: subida de imagen (multipart) ----
    print_step(3, "Subir imagen PNG (multipart)")
    r = client.post(
        f"{API_V1}/menu/items/{item_id}/imagen",
        headers=headers,
        files={"archivo": ("carta-test.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 200, f"Subida falló: {r.status_code} {r.text}"
    url1 = r.json()["imagen_url"]
    assert url1 and url1.startswith("/carta/img/platos/"), f"Ruta inesperada: {url1}"
    nombre1 = os.path.basename(url1)
    assert os.path.exists(os.path.join(UPLOAD_DIR, nombre1)), "Archivo no existe en disco"
    print_ok(f"Imagen guardada en {url1}")

    r = client.get(f"{API_PUBLIC}/item/{item_id}")
    assert r.json()["imagen_url"] == url1, "API pública no refleja la nueva imagen"
    print_ok("API pública refleja imagen_url")

    # ---- FASE 4: reemplazo de imagen (borra la anterior) ----
    print_step(4, "Reemplazar imagen con JPEG")
    r = client.post(
        f"{API_V1}/menu/items/{item_id}/imagen",
        headers=headers,
        files={"archivo": ("carta-test.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert r.status_code == 200, f"Reemplazo falló: {r.status_code} {r.text}"
    url2 = r.json()["imagen_url"]
    assert url2 != url1, "La ruta debería cambiar al reemplazar"
    assert not os.path.exists(os.path.join(UPLOAD_DIR, nombre1)), "El archivo anterior no se eliminó"
    print_ok(f"Nueva imagen {url2}; archivo anterior eliminado")

    # ---- FASE 5: validaciones ----
    print_step(5, "Validaciones: tipo no permitido y tamaño máximo")
    r = client.post(
        f"{API_V1}/menu/items/{item_id}/imagen",
        headers=headers,
        files={"archivo": ("malo.txt", b"no soy imagen", "text/plain")},
    )
    assert r.status_code == 400, f"Se esperaba 400 para tipo no permitido, got {r.status_code}"
    print_ok("Tipo .txt rechazado con 400")

    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post(
        f"{API_V1}/menu/items/{item_id}/imagen",
        headers=headers,
        files={"archivo": ("grande.png", grande, "image/png")},
    )
    assert r.status_code == 400, f"Se esperaba 400 por tamaño, got {r.status_code}"
    print_ok("Archivo > 5 MB rechazado con 400")

    # imagen_url no se debe poder forzar desde el body
    r = client.put(f"{API_V1}/menu/items/{item_id}", headers=headers, json={
        "imagen_url": "http://ejemplo.com/maliciosa.png",
    })
    assert r.status_code == 200, f"PUT falló: {r.status_code}"
    assert r.json().get("imagen_url") in (None, url2), "imagen_url NO debe aceptarse por body"
    print_ok("PUT ignora imagen_url (solo el servidor la asigna)")

    # ---- FASE 6: plato sin tiempo ----
    print_step(6, "Plato sin tiempo_preparacion queda null")
    r = client.post(f"{API_V1}/menu/items", headers=headers, json={
        "nombre": "Carta Test Sin Tiempo",
        "precio": "5.00",
        "categoria_id": cat_id,
    })
    assert r.status_code == 201, f"Creación falló: {r.status_code} {r.text}"
    item2 = r.json()
    assert item2["tiempo_preparacion"] is None and item2["imagen_url"] is None
    print_ok("Plato sin tiempo → campos null")

    # ---- FASE 7: limpieza ----
    print_step(7, "Limpieza de datos de prueba")
    for iid in (item2["id"], item_id):
        limpiar_archivos_upload(iid)
        client.delete(f"{API_V1}/menu/items/{iid}", headers=headers)
    client.delete(f"{API_V1}/menu/categorias/{cat_id}", headers=headers)
    print_ok("Platos, categoría y archivos de imagen eliminados")

    print_header("RESULTADO: TODAS LAS PRUEBAS DE LA CARTA PASARON")
    client.close()


if __name__ == "__main__":
    run_tests()
