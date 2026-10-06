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
    """Ejecuta consultas de calendario y asistencia con SQLAlchemy."""

    def __init__(self, db: Session):
        """Guarda la sesión de base de datos de la petición."""
        self.db = db

    def obtener_eventos(
        self,
        desde: date,
        hasta: date,
    ) -> list[tuple[EventoCalendario, str | None, str | None, str | None, str | None]]:
        """Lista eventos que se solapan con el rango y sus nombres de catálogo.

        El intervalo es inclusivo: incluye eventos que empiezan antes de
        ``desde`` si su ``fecha_fin`` llega hasta el rango. Un evento sin fecha
        final se trata como un evento de un solo día. Los outer joins conservan
        eventos aunque una referencia opcional no tenga nombre asociado.

        Args:
            desde: Primer día del rango consultado.
            hasta: Último día del rango consultado.

        Returns:
            Filas con el evento, nombre de platillo, nombre de insumo, nombre de
            proveedor y nombre de unidad base del insumo; los nombres pueden ser
            ``None``.
        """
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
        """Obtiene asistencias reales no anuladas junto con empleado y turno.

        El rango usa ``Asistencia.fecha`` (día calendario), no el día de
        negocio. Se ordenan los registros por fecha y hora de entrada para que
        la API pueda mostrarlos cronológicamente.

        Args:
            desde: Primer día calendario inclusivo.
            hasta: Último día calendario inclusivo.

        Returns:
            Diccionarios con IDs, nombres, turno, fecha y horas de entrada y
            salida. Los turnos abiertos mantienen ``hora_salida_real`` en
            ``None``.
        """
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
