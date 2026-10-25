from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tiempo import ahora_local, hoy_local
from app.utils.calculations import calcular_horas_extras
from app.models.personal import Usuario
from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.turno_repository import TurnoRepository
from app.repositories.empleado_repository import EmpleadoRepository
from app.schemas.asistencia import (
    TurnoCreate,
    TurnoUpdate,
    TurnoResponse,
    AsistenciaCheckIn,
    AsistenciaCheckOut,
    AsistenciaResponse,
    AsistenciaHorasExtrasUpdate,
    AsistenciaEditarHorarios,
    AsistenciaAnularRequest
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
        """
        turnos = self.turno_repo.get_all()
        return [TurnoResponse.model_validate(t) for t in turnos]

    def actualizar_turno(self, turno_id: int, datos: TurnoUpdate) -> TurnoResponse:
        """
        Actualiza un turno laboral existente.
        """
        turno = self.turno_repo.get_by_id(turno_id)
        if not turno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el turno con ID {turno_id}"
            )
        update_data = datos.model_dump(exclude_unset=True)
        if "nombre" in update_data and update_data["nombre"].lower() != turno.nombre.lower():
            if self.turno_repo.exists_by_nombre(update_data["nombre"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un turno con el nombre '{update_data['nombre']}'"
                )
        if update_data:
            self.turno_repo.update(turno_id, update_data)
            turno = self.turno_repo.get_by_id(turno_id)
        return TurnoResponse.model_validate(turno)

    def eliminar_turno(self, turno_id: int) -> None:
        """
        Elimina un turno laboral sin asistencias registradas.
        """
        turno = self.turno_repo.get_by_id(turno_id)
        if not turno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el turno con ID {turno_id}"
            )
        if turno.asistencias:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar '{turno.nombre}': tiene asistencias registradas."
            )
        self.turno_repo.delete(turno_id)

    # =========================================================================
    # Asistencia - Check In / Check Out
    # =========================================================================

    def registrar_entrada(
        self,
        checkin_in: AsistenciaCheckIn,
        ip_origen: str | None = None
    ) -> AsistenciaResponse:
        """
        Registra la entrada de un empleado permitiendo nuevo turno si el anterior ya finalizó.
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

        # CORRECCIÓN: Solo bloquear si el empleado tiene una sesión ABIERTA en este momento.
        if self.asistencia_repo.get_abierta_por_empleado(checkin_in.empleado_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El empleado ya tiene una sesión activa en este momento."
            )

        ahora = ahora_local()
        asistencia_data = {
            "empleado_id": checkin_in.empleado_id,
            "turno_id": checkin_in.turno_id,
            "fecha": ahora.date(),
            "hora_entrada_real": ahora,
            "observaciones": checkin_in.observaciones,
            "ip_origen": ip_origen
        }

        asistencia_creada = self.asistencia_repo.create(asistencia_data)
        return AsistenciaResponse.model_validate(asistencia_creada)

    def registrar_salida(self, checkout_in: AsistenciaCheckOut) -> AsistenciaResponse:
        """
        Registra la salida de un empleado y calcula horas extras.
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
                detail="Esta asistencia ya tiene registrada una salida."
            )

        ahora = ahora_local()
        
        # Cálculo seguro de horas extras
        horas_extras = Decimal("0.00")
        try:
            if asistencia.turno:
                horas_extras = calcular_horas_extras(
                    hora_entrada=asistencia.hora_entrada_real,
                    hora_salida=ahora,
                    horas_teoricas=asistencia.turno.horas_teoricas
                )
        except Exception:
            pass

        update_data = {
            "hora_salida_real": ahora,
            "horas_extras": horas_extras,
        }
        if checkout_in.observaciones:
            update_data["observaciones"] = checkout_in.observaciones

        asistencia_actualizada = self.asistencia_repo.update(asistencia.id, update_data)
        return AsistenciaResponse.model_validate(asistencia_actualizada)