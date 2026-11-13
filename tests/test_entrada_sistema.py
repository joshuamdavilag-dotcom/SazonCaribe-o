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


def test_el_visor_usa_touch_events_para_ios():
    """Safari en iOS no entrega pointermove de forma fiable: el visor escucha
    Touch Events con passive:false y evita el zoom/doble toque de la página."""
    js = _cliente().get(CARTA_RUTA_PUBLICA + "/js/menu-libro.js").text
    assert '"touchstart"' in js
    assert '"touchmove"' in js
    assert '"touchend"' in js
    assert "passive: false" in js
    assert 'evento.pointerType === "touch"' in js
    assert "setPointerCapture" in js
    assert "try {" in js


def test_el_visor_no_deja_que_ios_haga_scroll_ni_zoom_de_pagina():
    css = _cliente().get(CARTA_RUTA_PUBLICA + "/css/estilo.css").text
    visor = css.split(".visor {")[1].split("}")[0]
    lienzo = css.split(".visor-lienzo {")[1].split("}")[0]
    assert "touch-action: none" in visor
    assert "-webkit-touch-callout: none" in visor
    assert "overscroll-behavior: contain" in visor
    assert "touch-action: none" in lienzo
    assert "pointer-events: none" in css.split(".visor-img {")[1].split("}")[0]


def test_el_visor_explica_los_gestos():
    html = _cliente().get(CARTA_RUTA_PUBLICA + "/").text
    assert 'id="visor-pista"' in html
    assert "Pellizca" in html
    js = _cliente().get(CARTA_RUTA_PUBLICA + "/js/menu-libro.js").text
    assert "pistaVisor" in js


def test_en_celular_el_boton_ampliar_va_en_el_flujo():
    """En iOS el boton flotante puede quedar fuera de pantalla; en movil va
    dentro de la escena, junto al libro, como los controles del pie."""
    css = _cliente().get(CARTA_RUTA_PUBLICA + "/css/estilo.css").text
    bloques = css.split("@media (max-width: 820px)")
    assert "position: static" in bloques[-1].split(".btn-zoom {")[1].split("}")[0]
    assert ".escena" in bloques[1]


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
