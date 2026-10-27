from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.turno_service import calcular_nomina_quincenal
from app.services.nomina_service import NominaService


def test_calcular_nomina_quincenal_usa_salario_base_del_empleado():
    resultado = calcular_nomina_quincenal(3500.0, 2.0, 3000.0)

    assert resultado["salario_base"] == 3000.0
    assert resultado["pago_quincenal_base"] == 1500.0
    assert resultado["valor_hora_extra"] == 25.0
    assert resultado["pago_total_antes_iva"] == 1525.0


def test_calcular_nomina_quincenal_fallback_al_salario_mensual():
    resultado = calcular_nomina_quincenal(2500.0, 4.0, 0.0)

    assert resultado["salario_base"] == 2500.0
    assert resultado["pago_quincenal_base"] == 1250.0
    assert resultado["valor_hora_extra"] == 41.67
    assert resultado["pago_total_antes_iva"] == 1291.67


def test_calculo_real_de_nomina_redondea_pago_de_horas_extras_al_final():
    class AsistenciaRepositoryFalso:
        def get_finalizadas_por_rango(self, empleado_id, fecha_inicio, fecha_fin):
            return [SimpleNamespace(horas_extras=4)]

    servicio = object.__new__(NominaService)
    servicio.asistencia_repo = AsistenciaRepositoryFalso()
    servicio._obtener_total_adelantos = lambda empleado_id, inicio, fin: Decimal("0.00")
    empleado = SimpleNamespace(id=1, salario_base=2500)

    resultado = servicio._calcular_periodo(
        empleado,
        date(2026, 10, 1),
        date(2026, 10, 15),
    )

    assert resultado["pago_horas_extras"] == Decimal("41.67")
    assert resultado["pago_neto"] == Decimal("1291.67")


def _servicio_falso():
    class AsistenciaRepositoryFalso:
        def get_finalizadas_por_rango(self, empleado_id, fecha_inicio, fecha_fin):
            return []

    servicio = object.__new__(NominaService)
    servicio.asistencia_repo = AsistenciaRepositoryFalso()
    servicio._obtener_total_adelantos = lambda empleado_id, inicio, fin: Decimal("0.00")
    return servicio


def test_calculo_semanal_prorratea_salario_mensual():
    servicio = _servicio_falso()
    empleado = SimpleNamespace(id=1, salario_base=4000)

    resultado = servicio._calcular_periodo(
        empleado,
        date(2026, 10, 20),
        date(2026, 10, 26),
    )

    # 7 días × (4000 / 30) = 933.33
    assert resultado["salario_periodo_teorico"] == Decimal("933.33")
    assert resultado["pago_neto"] == Decimal("933.33")
    assert resultado["salario_semanal_teorico"] == Decimal("933.33")


def test_calculo_permite_cualquier_cantidad_de_dias():
    servicio = _servicio_falso()
    empleado = SimpleNamespace(id=1, salario_base=3000)

    tres_dias = servicio._calcular_periodo(
        empleado, date(2026, 10, 1), date(2026, 10, 3)
    )
    cuatro_dias = servicio._calcular_periodo(
        empleado, date(2026, 10, 1), date(2026, 10, 4)
    )
    doce_dias = servicio._calcular_periodo(
        empleado, date(2026, 10, 1), date(2026, 10, 12)
    )
    mes = servicio._calcular_periodo(
        empleado, date(2026, 10, 1), date(2026, 10, 30)
    )

    assert tres_dias["salario_periodo_teorico"] == Decimal("300.00")
    assert cuatro_dias["salario_periodo_teorico"] == Decimal("400.00")
    assert doce_dias["salario_periodo_teorico"] == Decimal("1200.00")
    assert mes["salario_periodo_teorico"] == Decimal("3000.00")
    assert tres_dias["salario_quincenal_teorico"] == Decimal("1500.00")


def test_calculo_rechaza_fechas_invertidas():
    servicio = _servicio_falso()
    empleado = SimpleNamespace(id=1, salario_base=3000)

    with pytest.raises(HTTPException) as error:
        servicio._calcular_periodo(
            empleado, date(2026, 10, 5), date(2026, 10, 1)
        )

    assert error.value.status_code == 400

