from fastapi.testclient import TestClient

from app.main import CARTA_RUTA_PUBLICA, app


def _cliente() -> TestClient:
    return TestClient(app, follow_redirects=False)


def test_sistema_interno_se_sirve_desde_la_raiz():
    """El ERP vive en / para que la URL no muestre /Templates/index.html."""
    respuesta = _cliente().get("/")
    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
    assert '<title>Sazón Caribeño — POS</title>' in respuesta.text


def test_raiz_no_se_cachea():
    respuesta = _cliente().get("/")
    assert respuesta.headers["cache-control"] == "no-cache"


def test_erp_usa_rutas_absolutas_de_assets():
    """Necesario para servirse igual desde / y desde /Templates/index.html."""
    html = _cliente().get("/").text
    assert 'href="/Templates/css/style.css"' in html
    assert 'href="/Templates/css/tailwind.min.css"' in html
    assert 'src="/Templates/js/app.js"' in html
    assert 'src="/Templates/Imagenes/Logo-nuevo.jpg"' in html


def test_ruta_antigua_del_erp_sigue_respondiendo():
    respuesta = _cliente().get("/Templates/index.html")
    assert respuesta.status_code == 200
    assert '<title>Sazón Caribeño — POS</title>' in respuesta.text


def test_carta_sigue_en_su_ruta_propia():
    respuesta = _cliente().get(CARTA_RUTA_PUBLICA + "/")
    assert respuesta.status_code == 200
    assert 'id="libro"' in respuesta.text


def test_carta_sirve_las_paginas_del_libro():
    respuesta = _cliente().get(CARTA_RUTA_PUBLICA + "/paginas/01.webp")
    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "public, max-age=604800"


def test_carta_sirve_el_motor_del_libro():
    respuesta = _cliente().get(CARTA_RUTA_PUBLICA + "/vendor/page-flip.browser.js")
    assert respuesta.status_code == 200


def test_carta_ofrece_zoom_para_leer_de_cerca():
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert 'id="btn-zoom"' in html
    assert 'id="visor"' in html
    assert "hidden" in html.split('id="visor"')[1][:60]
    assert "Ampliar" in html


def test_el_motor_del_libro_maneja_pellizco_y_rueda():
    js = _cliente().get(CARTA_RUTA_PUBLICA + "/js/menu-libro.js").text
    assert "pointerdown" in js
    assert "pointermove" in js
    assert "wheel" in js
    assert "fijarEscala" in js


def test_carta_tiene_selector_de_idioma():
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert 'id="btn-idioma-es"' in html
    assert 'id="btn-idioma-en"' in html
    assert 'aria-pressed="true"' in html.split('id="btn-idioma-es"')[1][:120]


def test_carta_sirve_las_paginas_en_ingles():
    cliente = _cliente()
    for numero in ("01", "11"):
        respuesta = cliente.get(CARTA_RUTA_PUBLICA + f"/paginas/en/{numero}.webp")
        assert respuesta.status_code == 200
        assert respuesta.headers["cache-control"] == "public, max-age=604800"


def test_el_motor_del_libro_cambia_de_idioma():
    js = _cliente().get(CARTA_RUTA_PUBLICA + "/js/menu-libro.js").text
    assert "paginas/en/" in js
    assert "cambiarIdioma" in js
    assert "carta_idioma" in js
    assert "idioma" in js


def test_carta_no_redirige_al_sistema():
    """La carta y el sistema son entradas independientes."""
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert "pos_token" not in html
