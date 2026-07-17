from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.salon import EstadoMesa
from app.schemas.salon import (
    ZonaCreate,
    ZonaResponse,
    MesaCreate,
    MesaUpdate,
    MesaResponse
)
from app.services.salon_service import SalonService

router = APIRouter()


def get_salon_service(db: Session = Depends(get_db)) -> SalonService:
    """
    Dependencia para inyectar el servicio de salón.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de SalonService.
    """
    return SalonService(db)


# =============================================================================
# Body simple para cambio de estado
# =============================================================================

class CambioEstadoRequest(BaseModel):
    """Esquema simple para cambiar el estado de una mesa."""
    nuevo_estado: EstadoMesa


# =============================================================================
# Endpoints de Zonas
# =============================================================================

@router.post(
    "/zonas",
    response_model=ZonaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear zona del restaurante",
    description="Registra una nueva zona en el restaurante (ej: Terraza, Barra).",
    tags=["Salón y Mesas"]
)
def crear_zona(
    zona_in: ZonaCreate,
    service: SalonService = Depends(get_salon_service)
) -> ZonaResponse:
    """
    Crea una nueva zona en el restaurante.

    - **nombre**: Nombre único de la zona (requerido)
    - **descripcion**: Descripción opcional de la zona
    """
    return service.crear_zona(zona_in)


@router.get(
    "/mapa",
    response_model=List[ZonaResponse],
    summary="Mapa completo del restaurante",
    description="Obtiene todas las zonas con sus mesas y estados actuales.",
    tags=["Salón y Mesas"]
)
def obtener_mapa_completo(
    service: SalonService = Depends(get_salon_service)
) -> List[ZonaResponse]:
    """
    Retorna el mapa completo del restaurante.

    Cada zona incluye:
    - Datos de la zona (nombre, descripción)
    - Lista de mesas con su estado actual (LIBRE, OCUPADA, etc.)
    """
    return service.obtener_mapa_completo()


@router.get(
    "/zonas",
    response_model=List[ZonaResponse],
    summary="Listar zonas",
    description="Lista todas las zonas del restaurante con sus mesas.",
    tags=["Salón y Mesas"]
)
def listar_zonas(
    service: SalonService = Depends(get_salon_service)
) -> List[ZonaResponse]:
    return service.listar_zonas()


@router.delete(
    "/zonas/{zona_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar zona",
    description="Elimina una zona que no tenga mesas asociadas.",
    tags=["Salón y Mesas"]
)
def eliminar_zona(
    zona_id: int = Path(..., gt=0, description="ID de la zona"),
    service: SalonService = Depends(get_salon_service)
) -> None:
    service.eliminar_zona(zona_id)


# =============================================================================
# Endpoints de Mesas
# =============================================================================

@router.post(
    "/mesas",
    response_model=MesaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear mesa",
    description="Registra una nueva mesa en una zona del restaurante.",
    tags=["Salón y Mesas"]
)
def crear_mesa(
    mesa_in: MesaCreate,
    service: SalonService = Depends(get_salon_service)
) -> MesaResponse:
    """
    Crea una nueva mesa en una zona.

    - **numero**: Número de la mesa (requerido, > 0)
    - **capacidad**: Número de comensales (default: 4)
    - **estado**: Estado inicial (default: LIBRE)
    - **zona_id**: ID de la zona (requerido)

    El sistema valida:
    - Que la zona exista
    - Que el número de mesa sea único dentro de la zona
    """
    return service.crear_mesa(mesa_in)


@router.get(
    "/mesas",
    response_model=List[MesaResponse],
    summary="Listar mesas",
    description="Obtiene las mesas del restaurante, opcionalmente filtradas por estado.",
    tags=["Salón y Mesas"]
)
def listar_mesas(
    estados: Optional[List[EstadoMesa]] = Query(
        default=None,
        description="Filtrar por estado(s). Ejemplo: ?estados=LIBRE&estados=RESERVADA"
    ),
    service: SalonService = Depends(get_salon_service)
) -> List[MesaResponse]:
    """
    Retorna la lista de mesas del restaurante.

    - **estados**: Filtrar por uno o más estados (opcional)

    Ejemplos de uso:
    - `GET /mesas` → Todas las mesas
    - `GET /mesas?estados=LIBRE` → Solo mesas libres
    - `GET /mesas?estados=LIBRE&estados=RESERVADA` → Libres y reservadas
    """
    return service.obtener_mesas(estados)


@router.patch(
    "/mesas/{mesa_id}/estado",
    response_model=MesaResponse,
    summary="Cambiar estado de mesa",
    description="Actualiza el estado de una mesa (para meseros).",
    tags=["Salón y Mesas"]
)
def cambiar_estado_mesa(
    mesa_id: int = Path(
        ...,
        gt=0,
        description="ID de la mesa"
    ),
    body: CambioEstadoRequest = ...,
    service: SalonService = Depends(get_salon_service)
) -> MesaResponse:
    """
    Cambia el estado de una mesa.

    - **mesa_id**: ID de la mesa (en la URL)
    - **nuevo_estado**: Nuevo estado en el body

    Estados disponibles:
    - **LIBRE**: Mesa disponible para nuevos clientes
    - **OCUPADA**: Mesa con clientes activos
    - **RESERVADA**: Mesa apartada para una reserva
    - **MANTENIMIENTO**: Mesa fuera de servicio
    """
    return service.cambiar_estado_mesa(mesa_id, body.nuevo_estado)


@router.put(
    "/mesas/{mesa_id}",
    response_model=MesaResponse,
    summary="Actualizar mesa",
    description="Actualiza número, capacidad, estado o zona de una mesa.",
    tags=["Salón y Mesas"]
)
def actualizar_mesa(
    mesa_id: int = Path(..., gt=0, description="ID de la mesa"),
    mesa_in: MesaUpdate = ...,
    service: SalonService = Depends(get_salon_service)
) -> MesaResponse:
    return service.actualizar_mesa(mesa_id, mesa_in)


@router.delete(
    "/mesas/{mesa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar mesa",
    description="Elimina una mesa que no esté ocupada.",
    tags=["Salón y Mesas"]
)
def eliminar_mesa(
    mesa_id: int = Path(..., gt=0, description="ID de la mesa"),
    service: SalonService = Depends(get_salon_service)
) -> None:
    service.eliminar_mesa(mesa_id)
