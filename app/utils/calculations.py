from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP


MAX_HORAS_EXTRAS = Decimal("99.99")


def calcular_horas_extras(
    entrada_real: datetime,
    salida_real: datetime,
    hora_entrada_turno: time,
    hora_salida_turno: time,
) -> Decimal:
    """Calcula extras desde la salida programada, incluso en turnos nocturnos."""
    if salida_real <= entrada_real:
        return Decimal("0.00")

    fechas_inicio_turno = [
        entrada_real.date() + timedelta(days=desfase)
        for desfase in (-1, 0, 1)
    ]
    inicio_programado = min(
        (
            datetime.combine(fecha, hora_entrada_turno)
            for fecha in fechas_inicio_turno
        ),
        key=lambda inicio: abs((entrada_real - inicio).total_seconds()),
    )
    fecha_salida_programada = inicio_programado.date()
    if hora_salida_turno <= hora_entrada_turno:
        fecha_salida_programada += timedelta(days=1)

    salida_programada = datetime.combine(
        fecha_salida_programada,
        hora_salida_turno,
    )
    segundos_extra = max(
        Decimal("0"),
        Decimal(str((salida_real - salida_programada).total_seconds())),
    )
    horas_extras = (segundos_extra / Decimal("3600")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return min(horas_extras, MAX_HORAS_EXTRAS)
