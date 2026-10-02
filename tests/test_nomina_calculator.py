from datetime import date
from decimal import Decimal
from types import SimpleNamespace

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
