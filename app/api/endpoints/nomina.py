from typing import List

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.nomina import (
    NominaGenerarRequest, NominaCalcularRequest, NominaResponse
)
from app.services.nomina_service import NominaService

router = APIRouter()


def get_nomina_service(db: Session = Depends(get_db)) -> NominaService:
    """
    Dependencia para inyectar el servicio de nómina.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de NominaService.
    """
    return NominaService(db)


# =============================================================================
# Endpoints de Generación de Nómina
# =============================================================================

@router.post(
    "/generar",
    response_model=List[NominaResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generar nómina quincenal",
    description="Genera masivamente las nóminas para un período quincenal específico.",
    tags=["Nóminas & Pagos"]
)
def generar_nomina(
    periodo: NominaGenerarRequest,
    service: NominaService = Depends(get_nomina_service)
) -> List[NominaResponse]:
    """
    Genera nóminas quincenales para todos los empleados activos.

    - **fecha_inicio**: Fecha de inicio del período quincenal
    - **fecha_fin**: Fecha de fin del período quincenal

    El sistema calcula automáticamente:
    - Salario quincenal teórico (mensual / 2)
    - Horas extras registradas en el período
    - Pago neto total

    Si un empleado ya tiene nómina generada para ese período, se omite.
    """
    return service.generar_nomina_quincenal(periodo)


@router.post(
    "/calcular",
    response_model=NominaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calcular nómina de un empleado",
    description=(
        "Calcula la nómina de un empleado específico para un período. "
        "Obtiene asistencias finalizadas, calcula horas normales "
        "y extras (tarifa normal 1.0x) y crea el registro."
    ),
    tags=["Nóminas & Pagos"]
)
def calcular_nomina(
    request: NominaCalcularRequest,
    service: NominaService = Depends(get_nomina_service)
) -> NominaResponse:
    """
    Calcula y crea la nómina para un empleado en un período dado.

    - **empleado_id**: ID del empleado
    - **fecha_inicio**: Fecha de inicio del período
    - **fecha_fin**: Fecha de fin del período

    El cálculo incluye:
    - Horas normales trabajadas × tarifa normal
    - Horas extras × tarifa normal (1.0x)
    - Pago neto total (sin deducciones)
    """
    return service.calcular_nomina_periodo(
        request.empleado_id,
        request.fecha_inicio,
        request.fecha_fin
    )


@router.get(
    "/pendientes",
    response_model=List[NominaResponse],
    summary="Listar nóminas pendientes",
    description="Obtiene todas las nóminas con estado 'PENDIENTE' de pago.",
    tags=["Nóminas & Pagos"]
)
def listar_pendientes(
    service: NominaService = Depends(get_nomina_service)
) -> List[NominaResponse]:
    """
    Retorna la lista de todas las nóminas pendientes de pago.

    Útil para conocer el monto total que se debe a los empleados
    antes de realizar los pagos.
    """
    return service.nominas_pendientes()


# =============================================================================
# Endpoints de Pago
# =============================================================================

@router.put(
    "/{nomina_id}/pagar",
    response_model=NominaResponse,
    summary="Pagar nómina",
    description="Cambia el estado de una nómina a 'PAGADO' y registra la fecha de pago.",
    tags=["Nóminas & Pagos"]
)
def pagar_nomina(
    nomina_id: int = Path(
        ...,
        gt=0,
        description="ID de la nómina a pagar"
    ),
    service: NominaService = Depends(get_nomina_service)
) -> NominaResponse:
    """
    Marca una nómina como pagada.

    - **nomina_id**: ID del registro de nómina

    El sistema asigna automáticamente la fecha y hora actual
    como fecha de pago. No se permite pagar una nómina ya pagada.
    """
    return service.pagar_nomina(nomina_id)


# =============================================================================
# Endpoints de Consulta
# =============================================================================

@router.get(
    "/empleados/{empleado_id}/historial",
    response_model=List[NominaResponse],
    summary="Historial de pagos del empleado",
    description="Obtiene el historial completo de nóminas de un empleado.",
    tags=["Nóminas & Pagos"]
)
def historial_empleado(
    empleado_id: int = Path(
        ...,
        gt=0,
        description="ID del empleado"
    ),
    service: NominaService = Depends(get_nomina_service)
) -> List[NominaResponse]:
    """
    Retorna el historial completo de nóminas de un empleado.

    El historial se ordena por fecha de forma descendente
    (más reciente primero), mostrando todos los períodos pagados
    y pendientes.
    """
    return service.historial_empleado(empleado_id)


@router.get(
    "/empleado/{empleado_id}",
    response_model=List[NominaResponse],
    summary="Historial de nóminas del empleado",
    description="Lista el historial de nóminas de un empleado específico.",
    tags=["Nóminas & Pagos"]
)
def obtener_historial_empleado(
    empleado_id: int = Path(
        ...,
        gt=0,
        description="ID del empleado"
    ),
    service: NominaService = Depends(get_nomina_service)
) -> List[NominaResponse]:
    """
    Retorna la lista de nóminas de un empleado.

    - **empleado_id**: ID del empleado a consultar

    Las nóminas se ordenan por fecha de forma descendente
    (más reciente primero).
    """
    return service.historial_empleado(empleado_id)
