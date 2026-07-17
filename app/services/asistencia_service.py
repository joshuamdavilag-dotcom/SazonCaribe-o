from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.turno_repository import TurnoRepository
from app.repositories.empleado_repository import EmpleadoRepository
from app.schemas.asistencia import (
    TurnoCreate,
    TurnoResponse,
    AsistenciaCheckIn,
    AsistenciaCheckOut,
    AsistenciaResponse,
    AsistenciaHorasExtrasUpdate
)


class AsistenciaService:
    """
    Servicio de lógica de negocio para el módulo de asistencia y turnos.

    Coordina las operaciones entre repositorios, validaciones
    y reglas de negocio del sistema.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.turno_repo = TurnoRepository(db)
        self.asistencia_repo = AsistenciaRepository(db)
        self.empleado_repo = EmpleadoRepository(db)

    # =========================================================================
    # Turnos
    # =========================================================================

    def crear_turno(self, turno_in: TurnoCreate) -> TurnoResponse:
        """
        Crea un nuevo turno laboral.

        Args:
            turno_in: Datos del turno a crear.

        Returns:
            TurnoResponse con el turno creado.

        Raises:
            HTTPException 400: Si ya existe un turno con ese nombre.
        """
        if self.turno_repo.exists_by_nombre(turno_in.nombre):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un turno con el nombre '{turno_in.nombre}'"
            )

        turno_data = turno_in.model_dump()
        turno_creado = self.turno_repo.create(turno_data)
        return TurnoResponse.model_validate(turno_creado)

    def obtener_turno(self, turno_id: int) -> TurnoResponse:
        """
        Obtiene un turno por su ID.

        Args:
            turno_id: ID del turno.

        Returns:
            TurnoResponse con los datos del turno.

        Raises:
            HTTPException 404: Si el turno no existe.
        """
        turno = self.turno_repo.get_by_id(turno_id)
        if not turno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el turno con ID {turno_id}"
            )
        return TurnoResponse.model_validate(turno)

    def listar_turnos(self) -> List[TurnoResponse]:
        """
        Lista todos los turnos registrados.

        Returns:
            Lista de TurnoResponse.
        """
        turnos = self.turno_repo.get_all()
        return [TurnoResponse.model_validate(t) for t in turnos]

    # =========================================================================
    # Asistencia - Check In / Check Out
    # =========================================================================

    def registrar_entrada(
        self,
        checkin_in: AsistenciaCheckIn,
        ip_origen: str | None = None
    ) -> AsistenciaResponse:
        """
        Registra la entrada de un empleado.

        Args:
            checkin_in: Datos del check-in.
            ip_origen: Dirección IP de origen (para auditoría).

        Returns:
            AsistenciaResponse con el registro creado.

        Raises:
            HTTPException 404: Si el empleado o turno no existen.
            HTTPException 400: Si el empleado ya registró entrada hoy.
        """
        empleado = self.empleado_repo.get_by_id(checkin_in.empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {checkin_in.empleado_id}"
            )

        turno = self.turno_repo.get_by_id(checkin_in.turno_id)
        if not turno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el turno con ID {checkin_in.turno_id}"
            )

        if self.asistencia_repo.tiene_registro_hoy(checkin_in.empleado_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El empleado ya registró su entrada para el día de hoy"
            )

        ahora = datetime.now()
        asistencia_data = {
            "empleado_id": checkin_in.empleado_id,
            "turno_id": checkin_in.turno_id,
            "fecha": date.today(),
            "hora_entrada_real": ahora,
            "observaciones": checkin_in.observaciones,
            "ip_origen": ip_origen
        }

        asistencia_creada = self.asistencia_repo.create(asistencia_data)
        return AsistenciaResponse.model_validate(asistencia_creada)

    def registrar_salida(self, checkout_in: AsistenciaCheckOut) -> AsistenciaResponse:
        """
        Registra la salida de un empleado y calcula horas extras.

        Args:
            checkout_in: Datos del check-out.

        Returns:
            AsistenciaResponse con el registro actualizado.

        Raises:
            HTTPException 404: Si la asistencia no existe.
            HTTPException 400: Si ya tiene registrada una salida.
        """
        asistencia = self.asistencia_repo.get_by_id(checkout_in.asistencia_id)
        if not asistencia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la asistencia con ID {checkout_in.asistencia_id}"
            )

        if asistencia.hora_salida_real is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta asistencia ya cuenta con marca de salida"
            )

        ahora = datetime.now()
        horas_trabajadas = (ahora - asistencia.hora_entrada_real).total_seconds() / 3600

        turno = self.turno_repo.get_by_id(asistencia.turno_id)
        horas_extras = Decimal("0.00")
        if horas_trabajadas > turno.horas_teoricas:
            horas_extras = Decimal(str(round(horas_trabajadas - turno.horas_teoricas, 2)))

        datos_actualizacion = {
            "hora_salida_real": ahora,
            "horas_extras": horas_extras
        }

        if checkout_in.observaciones:
            datos_actualizacion["observaciones"] = checkout_in.observaciones

        asistencia_actualizada = self.asistencia_repo.update(
            checkout_in.asistencia_id,
            datos_actualizacion
        )

        return AsistenciaResponse.model_validate(asistencia_actualizada)

    # =========================================================================
    # Consultas de Asistencia
    # =========================================================================

    def obtener_asistencia(self, asistencia_id: int) -> AsistenciaResponse:
        """
        Obtiene una asistencia por su ID.

        Args:
            asistencia_id: ID de la asistencia.

        Returns:
            AsistenciaResponse con los datos de la asistencia.

        Raises:
            HTTPException 404: Si la asistencia no existe.
        """
        asistencia = self.asistencia_repo.get_by_id(asistencia_id)
        if not asistencia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la asistencia con ID {asistencia_id}"
            )
        return AsistenciaResponse.model_validate(asistencia)

    def historial_empleado(
        self,
        empleado_id: int,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
    ) -> List[AsistenciaResponse]:
        """
        Obtiene el historial de asistencias de un empleado, con filtro de fechas opcional.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha inicio del filtro (opcional).
            fecha_fin: Fecha fin del filtro (opcional).

        Returns:
            Lista de AsistenciaResponse ordenada por fecha descendente.
        """
        if fecha_inicio and fecha_fin:
            asistencias = self.asistencia_repo.get_asistencias_por_rango_fechas(
                empleado_id, fecha_inicio, fecha_fin
            )
        else:
            asistencias = self.asistencia_repo.get_asistencias_por_empleado(empleado_id)
        return [AsistenciaResponse.model_validate(a) for a in asistencias]

    def actualizar_horas_extras(
        self,
        asistencia_id: int,
        data: AsistenciaHorasExtrasUpdate,
        gerente_id: int
    ) -> AsistenciaResponse:
        """
        Actualiza las horas extras de una asistencia con auditoría completa.

        Guarda las horas originales, el motivo de cambio y el ID del usuario
        autorizador para trazabilidad total.

        Args:
            asistencia_id: ID de la asistencia a modificar.
            data: Nuevas horas extras y motivo obligatorio.
            gerente_id: ID del usuario autenticado que autoriza el cambio.

        Returns:
            AsistenciaResponse con la asistencia actualizada.

        Raises:
            HTTPException 404: Si la asistencia no existe.
            HTTPException 400: Si el motivo está vacío.
        """
        asistencia = self.asistencia_repo.get_by_id(asistencia_id)
        if not asistencia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la asistencia con ID {asistencia_id}"
            )

        if not data.motivo or not data.motivo.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El motivo de la modificación es obligatorio para auditoría"
            )

        horas_originales = asistencia.horas_extras

        datos_actualizacion = {
            "horas_extras": data.horas_extras,
            "horas_extras_originales": horas_originales,
            "motivo_modificacion": data.motivo.strip(),
            "modificado_por": gerente_id,
        }

        asistencia_actualizada = self.asistencia_repo.update(
            asistencia_id,
            datos_actualizacion
        )
        return AsistenciaResponse.model_validate(asistencia_actualizada)

    def asistencias_del_dia(self, fecha: date = None) -> List[AsistenciaResponse]:
        """
        Obtiene todas las asistencias de un día específico.

        Args:
            fecha: Fecha a consultar (por defecto hoy).

        Returns:
            Lista de AsistenciaResponse.
        """
        if fecha is None:
            fecha = date.today()
        asistencias = self.asistencia_repo.get_asistencias_por_fecha(fecha)
        return [AsistenciaResponse.model_validate(a) for a in asistencias]

    def actualizar_heartbeat(self, asistencia_id: int) -> AsistenciaResponse:
        asistencia = self.asistencia_repo.get_by_id(asistencia_id)
        if not asistencia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la asistencia con ID {asistencia_id}",
            )
        if asistencia.hora_salida_real is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta asistencia ya tiene registrada una salida",
            )
        self.asistencia_repo.actualizar_heartbeat(asistencia_id)
        self.db.refresh(asistencia)
        return AsistenciaResponse.model_validate(asistencia)

    def cerrar_turnos_stale(
        self,
        timeout_seconds: int,
    ) -> int:
        timeout_desde = datetime.now() - timedelta(seconds=timeout_seconds)
        stale = self.asistencia_repo.get_activas_sin_heartbeat(timeout_desde)
        if not stale:
            return 0
        for asistencia in stale:
            fecha_fin = asistencia.ultimo_heartbeat or asistencia.hora_entrada_real
            horas_reales = (fecha_fin - asistencia.hora_entrada_real).total_seconds() / 3600
            turno = self.turno_repo.get_by_id(asistencia.turno_id)
            horas_extras = Decimal("0.00")
            if horas_reales > turno.horas_teoricas:
                horas_extras = Decimal(str(round(horas_reales - turno.horas_teoricas, 2)))
            self.asistencia_repo.update(
                asistencia.id,
                {
                    "hora_salida_real": fecha_fin,
                    "horas_extras": horas_extras,
                    "observaciones": "Cierre automático por timeout de heartbeat",
                },
            )
        return len(stale)
