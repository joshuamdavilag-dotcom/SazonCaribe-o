from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, requerir_permiso
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.schemas.caja import (
    CierreAutomaticoResponse,
    CierreAutomaticoUpdate,
    CierreCajaResponse,
    HistorialDiarioResponse,
    VentasDiaResponse,
)
from app.services.caja_service import CajaService

router = APIRouter()


def get_caja_service(db: Session = Depends(get_db)) -> CajaService:
    """Retorna el servicio de caja ligado a la sesión de BD de la petición."""
    return CajaService(db)


@router.get(
    "/historial-diario",
    response_model=HistorialDiarioResponse,
    summary="Historial de la caja actual",
    description=(
        "Devuelve las órdenes con estado PAGADA que aún no han sido "
        "archivadas en un cierre de caja (caja abierta)."
    ),
    dependencies=[Depends(get_current_user)],
)
def historial_diario(
    service: CajaService = Depends(get_caja_service),
) -> HistorialDiarioResponse:
    """Devuelve las órdenes pagadas de la caja abierta actual."""
    return service.historial_diario()


@router.get(
    "/ventas-dia",
    response_model=VentasDiaResponse,
    summary="Ventas del día (cualquier rol)",
    description=(
        "Resumen de solo lectura de las órdenes PAGADA de la caja abierta "
        "actual: total vendido, cantidad de órdenes y descuentos. "
        "No expone gastos, nómina ni utilidad. Disponible para todos los roles."
    ),
    dependencies=[Depends(get_current_user)],
)
def ventas_dia(
    current_user: Usuario = Depends(get_current_user),
    service: CajaService = Depends(get_caja_service),
) -> VentasDiaResponse:
    """Devuelve el resumen de ventas del día según el rol del usuario."""
    es_gestor = current_user.rol in (
        RolEnum.ADMINISTRADOR.value,
        RolEnum.GERENTE.value,
    )
    return service.ventas_dia(es_gestor)


@router.post(
    "/cierre",
    response_model=CierreCajaResponse,
    status_code=201,
    summary="Cerrar caja actual",
    description=(
        "Crea un registro de cierre de caja y archiva todas las órdenes "
        "PAGADA y gastos sin archivar. "
        "El siguiente ciclo de caja comienza en ceros."
    ),
    dependencies=[Depends(requerir_permiso("caja_cerrar"))],
)
def cerrar_caja(
    current_user: Usuario = Depends(get_current_user),
    service: CajaService = Depends(get_caja_service),
) -> CierreCajaResponse:
    """Cierra la caja actual y archiva las órdenes pagadas y gastos pendientes."""
    return service.cerrar_caja(current_user.id)


@router.get(
    "/cierre-automatico",
    response_model=CierreAutomaticoResponse,
    summary="Estado del cierre automático de caja",
    description=(
        "Indica si el cierre automático de medianoche (hora Managua) está "
        "habilitado, cuándo se ejecutó por última vez y cuándo será el próximo."
    ),
    dependencies=[Depends(get_current_user)],
)
def estado_cierre_automatico(
    service: CajaService = Depends(get_caja_service),
) -> CierreAutomaticoResponse:
    """Devuelve la configuración actual del cierre automático de caja."""
    return service.estado_cierre_automatico()


@router.put(
    "/cierre-automatico",
    response_model=CierreAutomaticoResponse,
    summary="Activar o desactivar el cierre automático de caja",
    description=(
        "Habilita o deshabilita el cierre de caja automático a las 12:00 AM "
        "(hora de Managua). Al habilitarlo, el primer cierre ocurre en la "
        "próxima medianoche. Los cierres automáticos quedan en la bitácora."
    ),
)
def configurar_cierre_automatico(
    body: CierreAutomaticoUpdate,
    current_user: Usuario = Depends(
        requerir_permiso("caja_cerrar")
    ),
    service: CajaService = Depends(get_caja_service),
) -> CierreAutomaticoResponse:
    """Actualiza la preferencia del cierre automático de caja."""
    return service.configurar_cierre_automatico(
        body.activo,
        usuario_id=current_user.id,
        actor_username=current_user.username,
        actor_rol=str(current_user.rol),
    )
