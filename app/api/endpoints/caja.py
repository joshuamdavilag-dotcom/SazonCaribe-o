from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, requerir_rol
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.schemas.caja import CierreCajaResponse, HistorialDiarioResponse, VentasDiaResponse
from app.services.caja_service import CajaService

router = APIRouter()


def get_caja_service(db: Session = Depends(get_db)) -> CajaService:
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
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def cerrar_caja(
    current_user: Usuario = Depends(get_current_user),
    service: CajaService = Depends(get_caja_service),
) -> CierreCajaResponse:
    return service.cerrar_caja(current_user.id)
