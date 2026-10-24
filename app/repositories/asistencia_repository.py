from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, and_, update, func, or_
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local, ventana_dia_negocio
from app.models.asistencia import Asistencia
from app.models.personal import Usuario
from app.repositories.base_repository import BaseRepository


class AsistenciaRepository(BaseRepository[Asistencia]):
    """
    Repositorio para el modelo Asistencia.

    Extiende BaseRepository con métodos específicos
    para la gestión de asistencias del personal.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Asistencia, db)

    def get_asistencia_del_dia(
        self,
        empleado_id: int,
        fecha: date
    ) -> Optional[Asistencia]:
        """
        Obtiene la asistencia de un empleado en un día específico.

        Args:
            empleado_id: ID del empleado.
            fecha: Fecha a consultar.

        Returns:
            La asistencia encontrada o None si no existe registro.
        """
        statement = select(Asistencia).where(
            Asistencia.empleado_id == empleado_id,
            Asistencia.fecha == fecha,
            Asistencia.anulada == False
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_asistencia_del_dia_negocio(
        self,
        empleado_id: int,
        ahora: datetime | None = None,
    ) -> Optional[Asistencia]:
        """
        Asistencia no anulada dentro del "día de negocio" vigente.

        El día de negocio es la ventana 7:00 AM → 7:00 AM (configurable via
        HORA_INICIO_DIA) para que los turnos de bar/restaurante que cruzan la
        medianoche no queden partidos entre dos fechas calendario. Se consulta
        por ``hora_entrada_real`` (no por la columna ``fecha``, que guarda el
        día calendario de creación y perdería los turnos de madrugada).

        Args:
            empleado_id: ID del empleado.
            ahora: Hora local de referencia (default: ahora mismo).

        Returns:
            La asistencia más antigua de la ventana o None.
        """
        inicio, fin = ventana_dia_negocio(ahora)
        statement = (
            select(Asistencia)
            .where(
                Asistencia.empleado_id == empleado_id,
                Asistencia.anulada == False,
                Asistencia.hora_entrada_real >= inicio,
                Asistencia.hora_entrada_real < fin,
            )
            .order_by(Asistencia.hora_entrada_real.asc())
        )
        return self.db.execute(statement).scalars().first()

    def get_asistencias_por_empleado(
        self,
        empleado_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Asistencia]:
        """
        Obtiene el historial completo de asistencias de un empleado.

        Args:
            empleado_id: ID del empleado.
            skip: Registros a omitir.
            limit: Número máximo de registros.

        Returns:
            Lista de asistencias ordenadas por fecha descendente.
        """
        statement = (
            select(Asistencia)
            .where(Asistencia.empleado_id == empleado_id)
            .order_by(Asistencia.fecha.desc())
            .offset(skip)
            .limit(limit)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_asistencias_por_fecha(
        self,
        fecha: date
    ) -> List[Asistencia]:
        """
        Obtiene todas las asistencias de un día específico.

        Args:
            fecha: Fecha a consultar.

        Returns:
            Lista de asistencias del día.
        """
        statement = (
            select(Asistencia)
            .where(Asistencia.fecha == fecha)
            .order_by(Asistencia.empleado_id)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_asistencias_por_turno_y_fecha(
        self,
        turno_id: int,
        fecha: date
    ) -> List[Asistencia]:
        """
        Obtiene las asistencias de un turno en un día específico.

        Args:
            turno_id: ID del turno.
            fecha: Fecha a consultar.

        Returns:
            Lista de asistencias del turno en esa fecha.
        """
        statement = (
            select(Asistencia)
            .where(
                Asistencia.turno_id == turno_id,
                Asistencia.fecha == fecha
            )
            .order_by(Asistencia.hora_entrada_real)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def tiene_registro_hoy(self, empleado_id: int) -> bool:
        """
        Verifica si el empleado ya tiene registro en el "día de negocio" vigente.

        "Hoy" abarca la ventana 7:00 AM → 7:00 AM (HORA_INICIO_DIA), no el día
        calendario, para que los turnos de bar/restaurante que cruzan la
        medianoche no queden partidos entre dos fechas.

        Args:
            empleado_id: ID del empleado.

        Returns:
            True si ya tiene registro, False si no.
        """
        return self.get_asistencia_del_dia_negocio(empleado_id) is not None

    def get_asistencias_por_rango_fechas(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date
    ) -> List[Asistencia]:
        """
        Obtiene las asistencias de un empleado en un rango de fechas.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del rango.
            fecha_fin: Fecha de fin del rango.

        Returns:
            Lista de asistencias en el rango especificado.
        """
        statement = (
            select(Asistencia)
            .where(
                Asistencia.empleado_id == empleado_id,
                Asistencia.fecha >= fecha_inicio,
                Asistencia.fecha <= fecha_fin,
                Asistencia.anulada == False
            )
            .order_by(Asistencia.fecha)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_finalizadas_por_rango(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date
    ) -> List[Asistencia]:
        """
        Obtiene asistencias finalizadas (check-out no nulo) en un rango de fechas.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del rango.
            fecha_fin: Fecha de fin del rango.

        Returns:
            Lista de asistencias finalizadas en el rango.
        """
        statement = (
            select(Asistencia)
            .where(
                Asistencia.empleado_id == empleado_id,
                Asistencia.fecha >= fecha_inicio,
                Asistencia.fecha <= fecha_fin,
                Asistencia.hora_salida_real.isnot(None),
                Asistencia.anulada == False
            )
            .order_by(Asistencia.fecha)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_activas_sin_heartbeat(
        self,
        timeout_desde: datetime,
    ) -> List[Asistencia]:
        """
        Asistencias activas (sin salida) cuyo dueño ya NO puede permanecer abierto.

        Un usuario mantiene el turno abierto si está activo y (no es Vendedor o
        tiene ``turno_habilitado``). Solo se auto-cierra lo "deshabilitado":
        vendedor con turno apagado, usuario inactivo o sin usuario vinculado.
        La línea base es el último heartbeat (o la hora de entrada si nunca hubo
        pulso) para incluir asistencias cuyo primer heartbeat nunca llegó.
        """
        usuario_puede_seguir = (
            select(Usuario.id)
            .where(
                Usuario.empleado_id == Asistencia.empleado_id,
                Usuario.activo == True,
                or_(
                    Usuario.rol != "Vendedor",
                    Usuario.turno_habilitado == True,
                ),
            )
            .exists()
        )
        statement = (
            select(Asistencia)
            .where(
                Asistencia.hora_salida_real.is_(None),
                Asistencia.anulada == False,
                func.coalesce(
                    Asistencia.ultimo_heartbeat,
                    Asistencia.hora_entrada_real,
                ) < timeout_desde,
                ~usuario_puede_seguir,
            )
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_abierta_por_empleado(
        self,
        empleado_id: int,
    ) -> Optional[Asistencia]:
        """Asistencia abierta (sin salida, no anulada) de un empleado, si existe."""
        statement = (
            select(Asistencia)
            .where(
                Asistencia.empleado_id == empleado_id,
                Asistencia.hora_salida_real.is_(None),
                Asistencia.anulada == False,
            )
            .order_by(Asistencia.id.asc())
        )
        return self.db.execute(statement).scalars().first()

    def get_abiertas_por_empleados(
        self,
        empleado_ids: List[int],
    ) -> List[Asistencia]:
        """Asistencias abiertas (sin salida, no anuladas) de varios empleados."""
        if not empleado_ids:
            return []
        statement = (
            select(Asistencia)
            .where(
                Asistencia.empleado_id.in_(empleado_ids),
                Asistencia.hora_salida_real.is_(None),
                Asistencia.anulada == False,
            )
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def actualizar_heartbeat(
        self,
        asistencia_id: int,
    ) -> Optional[Asistencia]:
        stmt = (
            update(Asistencia)
            .where(Asistencia.id == asistencia_id)
            .values(ultimo_heartbeat=ahora_local())
        )
        self.db.execute(stmt)
        self.db.commit()
        return self.get_by_id(asistencia_id)

    def auto_cerrar_stale(
        self,
        asistencia_id: int,
        hora_fin: datetime,
        horas_extras: Decimal,
        observaciones: str,
    ) -> bool:
        """
        Cierra automáticamente un turno stale SOLO si sigue abierto.

        El UPDATE condicional (`hora_salida_real IS NULL`) evita que la tarea
        de heartbeat sobreescriba la hora de salida de un check-out que el
        empleado acabó de registrar (carrera de condiciones).

        Returns:
            True si el turno se cerró, False si ya estaba finalizado.
        """
        stmt = (
            update(Asistencia)
            .where(
                Asistencia.id == asistencia_id,
                Asistencia.hora_salida_real.is_(None),
            )
            .values(
                hora_salida_real=hora_fin,
                horas_extras=horas_extras,
                observaciones=observaciones,
            )
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0
