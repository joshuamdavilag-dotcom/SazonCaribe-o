from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.asistencia import Asistencia
from app.models.calendario import EventoCalendario
from app.models.inventario import Insumo, Proveedor, UnidadMedida
from app.models.menu import MenuItem
from app.models.personal import Empleado
from app.models.asistencia import Turno


class CalendarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener_eventos(
        self,
        desde: date,
        hasta: date,
    ) -> list[tuple[EventoCalendario, str | None, str | None, str | None]]:
        return list(
            self.db.execute(
                select(
                    EventoCalendario,
                    MenuItem.nombre,
                    Insumo.nombre,
                    Proveedor.nombre,
                    UnidadMedida.nombre,
                )
                .outerjoin(MenuItem, EventoCalendario.menu_item_id == MenuItem.id)
                .outerjoin(Insumo, EventoCalendario.insumo_id == Insumo.id)
                .outerjoin(Proveedor, EventoCalendario.proveedor_id == Proveedor.id)
                .outerjoin(UnidadMedida, Insumo.unidad_medida_id == UnidadMedida.id)
                .where(
                    EventoCalendario.fecha_inicio <= hasta,
                    or_(
                        EventoCalendario.fecha_fin.is_(None),
                        EventoCalendario.fecha_fin >= desde,
                    ),
                )
                .order_by(EventoCalendario.fecha_inicio, EventoCalendario.hora_inicio, EventoCalendario.id)
            ).all()
        )

    def obtener_asistencias(self, desde: date, hasta: date) -> list[dict]:
        filas = self.db.execute(
            select(Asistencia, Empleado.nombre, Empleado.apellido, Turno.nombre)
            .join(Empleado, Asistencia.empleado_id == Empleado.id)
            .join(Turno, Asistencia.turno_id == Turno.id)
            .where(
                Asistencia.fecha >= desde,
                Asistencia.fecha <= hasta,
                Asistencia.anulada.is_(False),
            )
            .order_by(Asistencia.fecha, Asistencia.hora_entrada_real)
        )
        return [
            {
                "id": asistencia.id,
                "empleado_id": asistencia.empleado_id,
                "empleado_nombre": f"{nombre} {apellido}".strip(),
                "turno_nombre": turno_nombre,
                "fecha": asistencia.fecha,
                "hora_entrada_real": asistencia.hora_entrada_real,
                "hora_salida_real": asistencia.hora_salida_real,
            }
            for asistencia, nombre, apellido, turno_nombre in filas
        ]
