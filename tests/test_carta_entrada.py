from fastapi.testclient import TestClient

from app.main import CARTA_RUTA_PUBLICA, app


def _cliente() -> TestClient:
    return TestClient(app, follow_redirects=False)


def test_raiz_redirige_a_la_carta():
    respuesta = _cliente().get("/")
    assert respuesta.status_code == 302
    assert respuesta.headers["location"] == CARTA_RUTA_PUBLICA + "/"


def test_raiz_conserva_el_query_string():
    respuesta = _cliente().get("/?menu=1")
    assert respuesta.status_code == 302
    assert respuesta.headers["location"] == CARTA_RUTA_PUBLICA + "/?menu=1"


def test_carta_sirve_el_menu():
    respuesta = _cliente().get(CARTA_RUTA_PUBLICA + "/")
    assert respuesta.status_code == 200
    assert "Carta" in respuesta.text


def test_carta_reenvia_al_erp_si_hay_sesion():
    """El mismo enlace abre el sistema interno en equipos con sesión activa."""
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert "pos_token" in html
    assert "/Templates/index.html" in html
    assert "menu=1" in html


def test_carta_enlaza_al_acceso_del_personal():
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert 'id="link-personal"' in html
