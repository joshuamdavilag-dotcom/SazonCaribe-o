"""
Cierre de turnos huérfanos con la salida a las 18:00 (6:00 PM) del día de la entrada.

Sanea asistencias que quedaron abiertas (``hora_salida_real IS NULL``) de días
anteriores. Para cada registro huérfano calcula la salida como las 6:00 PM del
mismo día calendario de la entrada, recalcula las horas extras con la fórmula
normal (reales - teoricas, nunca negativas, tope de columna NUMERIC(4,2) => 99.99)
y deja el motivo de auditoría. Los registros de HOY (turnos legítimos aún activos)
NO se tocan. Es idempotente: los registros ya cerrados se ignoran.

Uso:
    python -m app.db.cerrar_turnos_huerfanos             # aplica y commitea
    python -m app.db.cerrar_turnos_huerfanos --dry-run   # simula y hace rollback
"""
import argparse
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.asistencia import Asistencia, Turno

HORA_CIERRE = time(18, 0)  # 6:00 PM
MAX_HORAS_EXTRAS = Decimal("99.99")
MOTIVO = "Cierre automático de turno huérfano (salida 6:00 PM del día de entrada)"


def _teoricas_de(a: Asistencia, db: Session) -> int:
    """Horas teóricas del turno vinculado, con fallback a 8."""
    turno = db.get(Turno, a.turno_id)
    return turno.horas_teoricas if turno else 8


def _cerrar_huérfanos(db: Session) -> None:
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
        print("No hay turnos huérfanos de días anteriores. Nada que hacer.")
        return

    print(f"{len(objetivo)} turno(s) huérfano(s) de días anteriores:\n")
    for a in objetivo:
        entrada = a.hora_entrada_real
        salida = datetime.combine(entrada.date(), HORA_CIERRE)
        if salida <= entrada:
            salida = entrada + timedelta(hours=8)
        teoricas = _teoricas_de(a, db)
        reales = (salida - entrada).total_seconds() / 3600
        extras = Decimal(str(round(max(reales - teoricas, 0.0), 2)))
        extras = min(extras, MAX_HORAS_EXTRAS)

        a.hora_salida_real = salida
        a.horas_extras = extras
        a.motivo_modificacion = MOTIVO

        print(
            f"  #{a.id}  empleado_id={a.empleado_id}  entrada={entrada:%Y-%m-%d %H:%M}  "
            f"-> salida={salida:%Y-%m-%d %H:%M}  extras={extras}h"
        )


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
        _cerrar_huérfanos(db)
        if args.dry_run:
            db.rollback()
            print("\n[dry-run] Cambios descartados (rollback).")
        else:
            db.commit()
            print("\nCambios aplicados y commiteados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()