from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select, and_, update
from sqlalchemy.orm import Session

from app.models.asistencia import Asistencia
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
            Asistencia.fecha == fecha
        )
        return self.db.execute(statement).scalar_one_or_none()

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
        Verifica si el empleado ya tiene registro de asistencia hoy.

        Args:
            empleado_id: ID del empleado.

        Returns:
            True si ya tiene registro, False si no.
        """
        return self.get_asistencia_del_dia(empleado_id, date.today()) is not None

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
                Asistencia.fecha <= fecha_fin
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
                Asistencia.hora_salida_real.isnot(None)
            )
            .order_by(Asistencia.fecha)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_activas_sin_heartbeat(
        self,
        timeout_desde: datetime,
    ) -> List[Asistencia]:
        statement = (
            select(Asistencia)
            .where(
                Asistencia.hora_salida_real.is_(None),
                Asistencia.ultimo_heartbeat.isnot(None),
                Asistencia.ultimo_heartbeat < timeout_desde,
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
            .values(ultimo_heartbeat=datetime.now())
        )
        self.db.execute(stmt)
        self.db.commit()
        return self.get_by_id(asistencia_id)
