from typing import List, Optional

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, requerir_rol
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.models.orden import EstadoOrden
from app.schemas.orden import (
    OrdenCreate,
    OrdenResponse,
    ActualizarEstadoOrden,
    AgregarItemsOrdenRequest,
)
from app.services.orden_service import OrdenService

router = APIRouter()


def get_orden_service(db: Session = Depends(get_db)) -> OrdenService:
    return OrdenService(db)


# =====================================================================
#  Crear orden
# =====================================================================

@router.post(
    "/",
    response_model=OrdenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir una nueva orden",
    description="Crea una orden con sus detalles. Descuenta inventario por receta.",
    dependencies=[Depends(get_current_user)],
)
def crear_orden(
    orden_in: OrdenCreate,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    return service.crear_orden(orden_in, current_user.id)


# =====================================================================
#  Listar órdenes
# =====================================================================

@router.get(
    "/",
    response_model=List[OrdenResponse],
    summary="Listar órdenes",
    description="Lista todas las órdenes con filtros opcionales por estado y mesa.",
    dependencies=[Depends(get_current_user)],
)
def listar_ordenes(
    estado: Optional[EstadoOrden] = None,
    mesa_id: Optional[int] = None,
    service: OrdenService = Depends(get_orden_service),
) -> List[OrdenResponse]:
    return service.obtener_ordenes(estado, mesa_id)


# =====================================================================
#  Obtener orden por ID
# =====================================================================

@router.get(
    "/{orden_id}",
    response_model=OrdenResponse,
    summary="Obtener orden por ID",
    description="Obtiene una orden específica con todos sus platos anidados.",
    dependencies=[Depends(get_current_user)],
)
def obtener_orden(
    orden_id: int = Path(..., gt=0),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    return service.obtener_orden(orden_id)


# =====================================================================
#  Actualizar estado (legacy)
# =====================================================================

@router.patch(
    "/{orden_id}/estado",
    response_model=OrdenResponse,
    summary="Actualizar estado de la orden",
    description="Modifica el estado de la orden en su ciclo de vida.",
    dependencies=[Depends(get_current_user)],
)
def actualizar_estado(
    orden_id: int = Path(..., gt=0),
    body: ActualizarEstadoOrden = ...,
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    return service.cambiar_estado(orden_id, body.estado)


# =====================================================================
#  Agregar ítems — POST canónico
# =====================================================================

@router.post(
    "/{orden_id}/items",
    response_model=OrdenResponse,
    status_code=status.HTTP_200_OK,
    summary="Agregar ítems a una orden existente",
    description=(
        "Añade nuevos productos a una orden abierta, acumula el total "
        "y descuenta los ingredientes del inventario."
    ),
    dependencies=[Depends(get_current_user)],
)
def agregar_items(
    orden_id: int = Path(..., gt=0),
    body: AgregarItemsOrdenRequest = ...,
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    return service.agregar_items_canonico(orden_id, body.items)


# =====================================================================
#  Pagar orden + liberar mesa
# =====================================================================

@router.put(
    "/{orden_id}/pagar",
    response_model=OrdenResponse,
    summary="Pagar orden y liberar mesa",
    description=(
        "Marca la orden como PAGADA y cambia el estado de la mesa "
        "vinculada a LIBRE en una sola transacción."
    ),
    dependencies=[Depends(get_current_user)],
)
def pagar_orden(
    orden_id: int = Path(..., gt=0),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    return service.pagar_orden(orden_id)
