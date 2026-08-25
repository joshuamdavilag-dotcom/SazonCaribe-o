from datetime import date, datetime
from zoneinfo import ZoneInfo

NICARAGUA_TZ = ZoneInfo("America/Managua")


def ahora_local() -> datetime:
    return datetime.now(NICARAGUA_TZ).replace(tzinfo=None)


def hoy_local() -> date:
    return ahora_local().date()
