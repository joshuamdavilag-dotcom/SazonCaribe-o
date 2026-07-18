from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.core.config import get_settings
from app.models.personal import Usuario
from app.repositories.asistencia_repository import AsistenciaRepository
from app.schemas.personal import RolEnum
from app.schemas.asistencia import (
    TurnoCreate,
    TurnoResponse,
    AsistenciaCheckIn,
    AsistenciaCheckOut,
    AsistenciaResponse,
    AsistenciaHorasExtrasUpdate
)
from app.services.asistencia_service import AsistenciaService
from app.services import turno_service

router = APIRouter()
settings = get_settings()


def get_asistencia_service(db: Session = Depends(get_db)) -> AsistenciaService:
    return AsistenciaService(db)


# =============================================================================
# Endpoints de Turnos
# =============================================================================

@router.post(
    "/turnos",
    response_model=TurnoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear turno laboral",
    description="Registra un nuevo turno laboral en el sistema.",
    tags=["Turnos"]
)
def crear_turno(
    turno_in: TurnoCreate,
    service: AsistenciaService = Depends(get_asistencia_service)
) -> TurnoResponse:
    """
    Crea un nuevo turno laboral.

    - **nombre**: Nombre único del turno (ej: "Matutino", "Nocturno")
    - **hora_entrada**: Hora de entrada (ej: "08:00:00")
    - **hora_salida**: Hora de salida (ej: "16:00:00")
    - **horas_teoricas**: Horas teóricas del turno (por defecto 8)
    """
    return service.crear_turno(turno_in)


@router.get(
    "/turnos",
    response_model=List[TurnoResponse],
    summary="Listar turnos",
    description="Obtiene la lista de todos los turnos laborales disponibles.",
    tags=["Turnos"]
)
def listar_turnos(
    service: AsistenciaService = Depends(get_asistencia_service)
) -> List[TurnoResponse]:
    """
    Retorna la lista de todos los turnos laborales registrados.
    """
    return service.listar_turnos()


@router.post(
    "/turnos/iniciar/{turno_id}",
    response_model=AsistenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar turno (check-in con validación de IP)",
    description=(
        "Registra la entrada de un empleado a su turno. "
        "Valida que la IP de origen coincida con la sede del restaurante "
        "si el usuario tiene rol Vendedor. Administradores y Gerentes "
        "están exentos de esta restricción."
    ),
    tags=["Turnos"]
)
def iniciar_turno(
    turno_id: int = Path(..., gt=0, description="ID del turno a iniciar"),
    request: Request = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsistenciaResponse:
    ip_origen = request.client.host if request and request.client else ""

    asistencia = turno_service.iniciar_turno(
        db=db,
        usuario_id=current_user.id,
        empleado_id=current_user.empleado_id,
        turno_id=turno_id,
        ip_cliente=ip_origen,
        rol=current_user.rol,
    )

    return AsistenciaResponse.model_validate(asistencia)


@router.post(
    "/turnos/heartbeat/{asistencia_id}",
    response_model=AsistenciaResponse,
    summary="Heartbeat de turno activo",
    description=(
        "Actualiza el timestamp de último pulso para evitar cierre automático. "
        "Si el cliente deja de enviar heartbeats por más de "
        "HEARTBEAT_TIMEOUT_SECONDS, el turno se cierra automáticamente."
    ),
    tags=["Turnos"]
)
def heartbeat_turno(
    asistencia_id: int = Path(..., gt=0, description="ID de la asistencia activa"),
    service: AsistenciaService = Depends(get_asistencia_service)
) -> AsistenciaResponse:
    return service.actualizar_heartbeat(asistencia_id)


# =============================================================================
# Endpoints de Asistencia (Check-In / Check-Out)
# =============================================================================

@router.post(
    "/check-in",
    response_model=AsistenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Marcar entrada",
    description="Registra la entrada de un empleado a su turno.",
    tags=["Asistencia"]
)
def registrar_entrada(
    checkin_in: AsistenciaCheckIn,
    request: Request = None,
    service: AsistenciaService = Depends(get_asistencia_service)
) -> AsistenciaResponse:
    """
    Registra la entrada de un empleado.

    - **empleado_id**: ID del empleado que marca entrada
    - **turno_id**: ID del turno al que pertenece
    - **observaciones**: Observaciones opcionales (ej: tardanza justificada)

    La fecha y hora de entrada se asignan automáticamente en el servidor.
    """
    ip_origen = request.client.host if request and request.client else None
    return service.registrar_entrada(checkin_in, ip_origen=ip_origen)


@router.post(
    "/check-out",
    response_model=AsistenciaResponse,
    summary="Marcar salida",
    description="Finaliza el turno activo del empleado logueado y calcula horas extras.",
    tags=["Asistencia"]
)
def registrar_salida(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsistenciaResponse:
    repo = AsistenciaRepository(db)
    asistencias = repo.get_asistencias_por_empleado(current_user.empleado_id)
    activa = next(
        (a for a in asistencias if a.hora_salida_real is None),
        None,
    )
    if not activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El empleado no tiene un turno activo para finalizar",
        )

    asistencia = turno_service.finalizar_turno(db, activa.id)
    return AsistenciaResponse.model_validate(asistencia)


# =============================================================================
# Endpoints de Consulta
# =============================================================================

@router.get(
    "/empleados/{empleado_id}/historial",
    response_model=List[AsistenciaResponse],
    summary="Historial de asistencia del empleado",
    description="Obtiene todo el historial de asistencias de un empleado, con filtro de fechas opcional.",
    tags=["Asistencia"]
)
def historial_empleado(
    empleado_id: int = Path(
        ...,
        gt=0,
        description="ID del empleado"
    ),
    fecha_inicio: Optional[date] = Query(None, description="Fecha inicio del filtro"),
    fecha_fin: Optional[date] = Query(None, description="Fecha fin del filtro"),
    service: AsistenciaService = Depends(get_asistencia_service)
) -> List[AsistenciaResponse]:
    """
    Retorna el historial de asistencias de un empleado.

    Si se proporcionan fecha_inicio y fecha_fin, filtra por ese rango.
    Caso contrario retorna todo el historial ordenado por fecha descendente.
    """
    return service.historial_empleado(empleado_id, fecha_inicio, fecha_fin)


@router.put(
    "/{asistencia_id}/horas-extras",
    response_model=AsistenciaResponse,
    summary="Actualizar horas extras con auditoría",
    description=(
        "Modifica las horas extras de un registro de asistencia. "
        "Requiere un motivo obligatorio para trazabilidad. "
        "Solo Administradores y Gerentes pueden realizar esta operación."
    ),
    tags=["Asistencia"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def actualizar_horas_extras(
    asistencia_id: int,
    data: AsistenciaHorasExtrasUpdate,
    current_user: Usuario = Depends(get_current_user),
    service: AsistenciaService = Depends(get_asistencia_service)
) -> AsistenciaResponse:
    """
    Actualiza las horas extras de una asistencia.

    - **asistencia_id**: ID de la asistencia a modificar
    - **horas_extras**: Nuevas horas extras (≥ 0)
    - **motivo**: Motivo del cambio (obligatorio)

    Se guarda en la base de datos:
    - Las horas extras originales antes del cambio
    - El motivo de la modificación
    - El ID del usuario que autorizó el cambio
    """
    return service.actualizar_horas_extras(asistencia_id, data, current_user.id)
