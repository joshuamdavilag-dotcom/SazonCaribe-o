"""
Cierre de turnos huérfanos con la salida a las 18:00 (6:00 PM) del día de la entrada.

Sanea asistencias que quedaron abiertas (``hora_salida_real IS NULL``) de días
anteriores. Para cada registro huérfano calcula la salida como las 6:00 PM del
mismo día calendario de la entrada, recalcula las horas extras desde la salida
programada del turno (nunca negativas, tope de columna NUMERIC(4,2) => 99.99)
y deja el motivo de auditoría. Los registros de HOY (turnos legítimos aún activos)
NO se tocan. Es idempotente: los registros ya cerrados se ignoran.

Se ejecuta automáticamente en el arranque de la app (``app/main.py``) y también
puede correrse como script:

Uso:
    python -m app.db.cerrar_turnos_huerfanos             # aplica y commitea
    python -m app.db.cerrar_turnos_huerfanos --dry-run   # simula y hace rollback
"""
import argparse
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.asistencia import Asistencia, Turno
from app.utils.calculations import calcular_horas_extras

HORA_CIERRE = time(18, 0)  # 6:00 PM
MAX_HORAS_EXTRAS = Decimal("99.99")
MOTIVO = "Cierre automático de turno huérfano (salida 6:00 PM del día de entrada)"


def _teoricas_de(a: Asistencia, db: Session) -> int:
    """Horas teóricas del turno vinculado, con fallback a 8."""
    turno = db.get(Turno, a.turno_id)
    return turno.horas_teoricas if turno else 8


def sancar_turnos_huerfanos(db: Session) -> List[Asistencia]:
    """Cierra turnos huérfanos de días anteriores con salida a las 18:00.

    Aplica los cambios en la sesión recibida (la fila a 6:00 PM del día de su
    entrada, horas extras recalculadas y motivo de auditoría) y devuelve la
    lista de asistencias afectadas, vacía si no hay nada que hacer. El cierre
    de la transacción (commit/rollback) queda a cargo del llamador.

    Returns:
        Lista de asistencias que se cerraron (vacía si no hubo).
    """
    hoy = date.today()
    abiertas = db.execute(
        select(Asistencia)
        .where(
            Asistencia.hora_salida_real.is_(None),
            Asistencia.anulada == False,
        )
        .order_by(Asistencia.id.asc())
    ).scalars().all()

    objetivo = [a for a in abiertas if a.hora_entrada_real.date() < hoy]
    if not objetivo:
        return []

    for a in objetivo:
        entrada = a.hora_entrada_real
        salida = datetime.combine(entrada.date(), HORA_CIERRE)
        if salida <= entrada:
            salida = entrada + timedelta(hours=8)
        turno = db.get(Turno, a.turno_id)
        if turno:
            extras = calcular_horas_extras(
                entrada,
                salida,
                turno.hora_entrada,
                turno.hora_salida,
            )
        else:
            teoricas = _teoricas_de(a, db)
            reales = (salida - entrada).total_seconds() / 3600
            extras = Decimal(str(round(max(reales - teoricas, 0.0), 2)))
            extras = min(extras, MAX_HORAS_EXTRAS)

        a.hora_salida_real = salida
        a.horas_extras = extras
        a.motivo_modificacion = MOTIVO

        print(
            f"  #[{a.id}]  empleado_id={a.empleado_id}  "
            f"entrada={entrada:%Y-%m-%d %H:%M}  "
            f"-> salida={salida:%Y-%m-%d %H:%M}  extras={extras}h"
        )
    return objetivo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cierra turnos huérfanos con salida a las 18:00 del día de entrada."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula los cambios y hace rollback (no persiste nada).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cerrados = sancar_turnos_huerfanos(db)
        if not cerrados:
            print("No hay turnos huérfanos de días anteriores. Nada que hacer.")
        if args.dry_run:
            db.rollback()
            print("\n[dry-run] Cambios descartados (rollback).")
        else:
            db.commit()
            print(f"\n{len(cerrados)} turno(s) cerrado(s) y commiteado(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()