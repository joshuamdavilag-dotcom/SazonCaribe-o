from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status
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
    EditarOrdenRequest,
    VentaRetroactivaCreate,
    AplicarDescuentoItemRequest,
    AplicarDescuentoGlobalRequest,
    AnularOrdenRequest,
    DevolverItemRequest,
)
from app.services.orden_service import OrdenService
from app.services.push_service import ejecutar_notificacion_push

router = APIRouter()


def get_orden_service(db: Session = Depends(get_db)) -> OrdenService:
    """Retorna el servicio de órdenes ligado a la sesión de BD de la petición."""
    return OrdenService(db)


# =====================================================================
#  Venta retroactiva (antes de /{orden_id} para evitar conflicto)
# =====================================================================

@router.post(
    "/retroactiva",
    response_model=OrdenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar venta de días pasados",
    description=(
        "Crea y paga directamente una orden con fecha específica del pasado. "
        "No descuenta inventario ni bloquea mesas."
    ),
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def crear_venta_retroactiva(
    venta_in: VentaRetroactivaCreate,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Registra y paga una orden con fecha pasada, sin afectar inventario ni mesas."""
    return service.crear_venta_retroactiva(venta_in, current_user.id)


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
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Abre una nueva orden con sus detalles y descuenta el inventario por receta."""
    orden = service.crear_orden(orden_in, current_user.id, current_user)
    background_tasks.add_task(ejecutar_notificacion_push, orden.id, "nueva_comanda")
    return orden


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
    """Lista las órdenes con filtros opcionales por estado y mesa."""
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
    """Devuelve una orden específica con todos sus detalles."""
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
    background_tasks: BackgroundTasks,
    orden_id: int = Path(..., gt=0),
    body: ActualizarEstadoOrden = ...,
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Cambia el estado de la orden validando la transición del ciclo de vida."""
    orden = service.cambiar_estado(orden_id, body.estado)
    if orden.estado == EstadoOrden.ENTREGADA:
        background_tasks.add_task(ejecutar_notificacion_push, orden.id, "comanda_lista")
    return orden


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
    background_tasks: BackgroundTasks,
    orden_id: int = Path(..., gt=0),
    body: AgregarItemsOrdenRequest = ...,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Agrega ítems a una orden abierta y descuenta los ingredientes del inventario."""
    orden = service.agregar_items_canonico(orden_id, body.items, current_user)
    background_tasks.add_task(ejecutar_notificacion_push, orden.id, "nueva_comanda")
    return orden


# =====================================================================
#  Editar comanda abierta (reemplaza el contenido) — PUT canónico
# =====================================================================

@router.put(
    "/{orden_id}/items",
    response_model=OrdenResponse,
    summary="Editar los ítems de una comanda abierta",
    description=(
        "Reemplaza el contenido de la comanda: actualiza cantidades y "
        "descuentos de los ítems existentes, agrega los nuevos y elimina "
        "los que no aparezcan en la lista enviada. Ajusta inventario."
    ),
    dependencies=[Depends(get_current_user)],
)
def editar_items(
    background_tasks: BackgroundTasks,
    orden_id: int = Path(..., gt=0),
    body: EditarOrdenRequest = ...,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Reemplaza el contenido de una comanda abierta y ajusta el inventario."""
    orden = service.editar_orden(orden_id, body.items, current_user)
    background_tasks.add_task(ejecutar_notificacion_push, orden.id, "nueva_comanda")
    return orden


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
    """Marca la orden como pagada y libera la mesa vinculada en una sola transacción."""
    return service.pagar_orden(orden_id)


# =====================================================================
#  Anulación / devolución de pedidos cobrados (Admin/Gerente)
# =====================================================================

@router.post(
    "/{orden_id}/anular",
    response_model=OrdenResponse,
    summary="Anular una orden pagada",
    description=(
        "Anula una orden PAGADA de la caja abierta (devolución total). "
        "Requiere `motivo` obligatorio; la orden deja de contar en ventas "
        "pero se conserva con autor, fecha y motivo en la auditoría."
    ),
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def anular_orden(
    orden_id: int,
    body: AnularOrdenRequest,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Anula una orden pagada dejando el motivo en auditoría."""
    return service.anular_orden(orden_id, body.motivo, current_user)


@router.post(
    "/{orden_id}/devolver-item",
    response_model=OrdenResponse,
    summary="Devolver unidades de una línea de la orden",
    description=(
        "Devuelve parte o todas las unidades de una línea de una orden PAGADA "
        "y recalcula el total. Requiere `motivo` obligatorio; queda en auditoría."
    ),
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def devolver_item(
    orden_id: int,
    body: DevolverItemRequest,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Devuelve unidades de una línea de una orden pagada."""
    return service.devolver_item(
        orden_id, body.detalle_id, body.cantidad, body.motivo, current_user
    )


# =====================================================================
#  Descuentos
# =====================================================================

@router.post(
    "/{orden_id}/descuento-item",
    response_model=OrdenResponse,
    summary="Aplicar descuento a un ítem de la orden",
    description="Aplica descuento porcentual o monto fijo a un DetalleOrden específico.",
    dependencies=[Depends(get_current_user)],
)
def aplicar_descuento_item(
    orden_id: int = Path(..., gt=0),
    body: AplicarDescuentoItemRequest = ...,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Aplica un descuento porcentual o de monto fijo a un ítem específico."""
    return service.aplicar_descuento_item(
        orden_id, body.detalle_id, body.tipo, body.valor, body.motivo, current_user
    )


@router.post(
    "/{orden_id}/descuento-global",
    response_model=OrdenResponse,
    summary="Aplicar descuento global a la orden",
    description="Aplica descuento porcentual o monto fijo al total de la orden, repartido entre todos los ítems.",
    dependencies=[Depends(get_current_user)],
)
def aplicar_descuento_global(
    orden_id: int = Path(..., gt=0),
    body: AplicarDescuentoGlobalRequest = ...,
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Aplica un descuento global repartido proporcionalmente entre los ítems."""
    return service.aplicar_descuento_global(
        orden_id, body.tipo, body.valor, body.motivo, current_user
    )


@router.delete(
    "/{orden_id}/descuento-item/{detalle_id}",
    response_model=OrdenResponse,
    summary="Quitar descuento de un ítem",
    description="Elimina el descuento aplicado a un DetalleOrden específico.",
    dependencies=[Depends(get_current_user)],
)
def quitar_descuento_item(
    orden_id: int = Path(..., gt=0),
    detalle_id: int = Path(..., gt=0),
    current_user: Usuario = Depends(get_current_user),
    service: OrdenService = Depends(get_orden_service),
) -> OrdenResponse:
    """Elimina el descuento aplicado a un detalle específico de la orden."""
    return service.quitar_descuento_item(orden_id, detalle_id, current_user)
