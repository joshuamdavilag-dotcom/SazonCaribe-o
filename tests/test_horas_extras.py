from datetime import datetime, time
from decimal import Decimal

from app.utils.calculations import calcular_horas_extras


def test_horas_extras_diurnas_solo_cuenta_despues_de_salida_programada():
    resultado = calcular_horas_extras(
        datetime(2026, 10, 2, 9, 0),
        datetime(2026, 10, 2, 17, 30),
        time(8, 0),
        time(16, 0),
    )

    assert resultado == Decimal("1.50")


def test_no_hay_horas_extras_si_sale_antes_de_hora_programada():
    resultado = calcular_horas_extras(
        datetime(2026, 10, 2, 8, 0),
        datetime(2026, 10, 2, 15, 30),
        time(8, 0),
        time(16, 0),
    )

    assert resultado == Decimal("0.00")


def test_horas_extras_en_turno_que_cruza_medianoche():
    resultado = calcular_horas_extras(
        datetime(2026, 10, 2, 23, 0),
        datetime(2026, 10, 3, 7, 0),
        time(22, 0),
        time(6, 0),
    )

    assert resultado == Decimal("1.00")


def test_turno_nocturno_iniciado_despues_de_medianoche():
    resultado = calcular_horas_extras(
        datetime(2026, 10, 3, 1, 0),
        datetime(2026, 10, 3, 7, 0),
        time(22, 0),
        time(6, 0),
    )

    assert resultado == Decimal("1.00")


def test_turno_nocturno_entrada_cerca_de_la_hora_de_salida():
    resultado = calcular_horas_extras(
        datetime(2026, 10, 3, 6, 30),
        datetime(2026, 10, 3, 7, 0),
        time(22, 0),
        time(6, 0),
    )

    assert resultado == Decimal("1.00")
