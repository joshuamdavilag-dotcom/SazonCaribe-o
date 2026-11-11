import string

import pytest

from app.core.slug import ALFABETO, generar_slug_publico


def test_slug_largo_por_defecto():
    assert len(generar_slug_publico()) == 10


def test_slug_respeta_largo_solicitado():
    assert len(generar_slug_publico(6)) == 6
    assert len(generar_slug_publico(32)) == 32


def test_slug_solo_letras_minusculas_y_digitos():
    permitidos = set(string.ascii_lowercase + string.digits)
    for _ in range(50):
        slug = generar_slug_publico(16)
        assert set(slug) <= permitidos


def test_slug_es_impredecible():
    generados = {generar_slug_publico(12) for _ in range(200)}
    assert len(generados) == 200


def test_alfabeto_sin_caracteres_reservados_de_url():
    for caracter in "/?#&=% .":
        assert caracter not in ALFABETO


@pytest.mark.parametrize("largo", [0, 5, 65, 100])
def test_largo_invalido(largo):
    with pytest.raises(ValueError):
        generar_slug_publico(largo)
