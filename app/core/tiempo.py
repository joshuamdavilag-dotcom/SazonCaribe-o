from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

NICARAGUA_TZ = ZoneInfo("America/Managua")


def ahora_local() -> datetime:
    return datetime.now(NICARAGUA_TZ).replace(tzinfo=None)


def hoy_local() -> date:
    return ahora_local().date()


def ventana_dia_negocio(
    t: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Ventana del "día de negocio" (hoy laboral) que contiene a ``t``.

    Como un bar/restaurante vive turnos que cruzan la medianoche, el "hoy" NO
    se corta a las 00:00 sino a la hora configurable ``HORA_INICIO_DIA``
    (default 7:00 AM). Un turno iniciado a la 1:00 AM del día calendario X+1
    pertenece al servicio del día de negocio X, es decir a la ventana
    ``[X 07:00, X+1 07:00)``.

    Args:
        t: Fecha/hora local (naive). Si es None, usa ahora mismo.

    Returns:
        Tupla ``(inicio, fin)`` (datetime naive) de la ventana de 24h vigente.

    Examples:
        - t = 2026-09-27 22:00 -> (2026-09-27 07:00, 2026-09-28 07:00)
        - t = 2026-09-28 01:00 -> (2026-09-27 07:00, 2026-09-28 07:00)
        - t = 2026-09-28 06:59 -> (2026-09-27 07:00, 2026-09-28 07:00)
        - t = 2026-09-28 07:00 -> (2026-09-28 07:00, 2026-09-29 07:00)
    """
    t = t or ahora_local()
    hora_inicio = get_settings().HORA_INICIO_DIA
    dia_negocio = (t - timedelta(hours=hora_inicio)).date()
    inicio = datetime.combine(dia_negocio, time(hora_inicio))
    return inicio, inicio + timedelta(days=1)