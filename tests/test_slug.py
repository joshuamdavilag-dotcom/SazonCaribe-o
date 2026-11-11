import string

import pytest

from app.core.slug import ALFABETO, generar_slug_publico


def test_slug_largo_por_defecto():
    slug = generar_slug_publico()
    prefijo, _, cuerpo = slug.partition("-")
    assert prefijo == "web"
    assert len(cuerpo) == 20


def test_slug_respeta_largo_y_prefijo():
    slug = generar_slug_publico(8, "mnu")
    prefijo, _, cuerpo = slug.partition("-")
    assert prefijo == "mnu"
    assert len(cuerpo) == 8


def test_slug_tiene_formato_tipo_render():
    slug = generar_slug_publico()
    assert slug.count("-") == 1
    assert slug.startswith("web-")


def test_slug_solo_letras_minusculas_y_digitos():
    permitidos = set(string.ascii_lowercase + string.digits)
    for _ in range(50):
        slug = generar_slug_publico(16)
        assert set(slug) <= permitidos | {"-"}
        assert set(slug.partition("-")[2]) <= permitidos


def test_slug_es_impredecible():
    generados = {generar_slug_publico(12) for _ in range(200)}
    assert len(generados) == 200


def test_alfabeto_sin_caracteres_reservados_de_url():
    for caracter in "/?#&=% .":
        assert caracter not in ALFABETO


@pytest.mark.parametrize("largo", [0, 7, 65, 100])
def test_largo_invalido(largo):
    with pytest.raises(ValueError):
        generar_slug_publico(largo)


@pytest.mark.parametrize("prefijo", ["", "   ", "a b", "x/y", "z" * 13, "ñ"])
def test_prefijo_invalido(prefijo):
    with pytest.raises(ValueError):
        generar_slug_publico(10, prefijo)


def test_prefijo_se_normaliza():
    slug = generar_slug_publico(10, "  MNU  ")
    assert slug.startswith("mnu-")
