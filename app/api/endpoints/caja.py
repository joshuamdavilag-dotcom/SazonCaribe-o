from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, requerir_rol
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.schemas.caja import CierreCajaResponse, HistorialDiarioResponse
from app.services.caja_service import CajaService

router = APIRouter()


def get_caja_service(db: Session = Depends(get_db)) -> CajaService:
    return CajaService(db)


@router.get(
    "/historial-diario",
    response_model=HistorialDiarioResponse,
    summary="Historial de órdenes pagadas del día",
    description=(
        "Devuelve las órdenes con estado PAGADA de la fecha actual "
        "que aún no han sido archivadas en un cierre de caja."
    ),
    dependencies=[Depends(get_current_user)],
)
def historial_diario(
    fecha: date | None = None,
    service: CajaService = Depends(get_caja_service),
) -> HistorialDiarioResponse:
    fecha_consulta = fecha or date.today()
    return service.historial_diario(fecha_consulta)


@router.post(
    "/cierre",
    response_model=CierreCajaResponse,
    status_code=201,
    summary="Cerrar caja del día",
    description=(
        "Crea un registro de cierre de caja y archiva todas las órdenes "
        "PAGADA de la fecha actual que no estén archivadas. "
        "El siguiente ciclo de caja comienza en ceros."
    ),
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def cerrar_caja(
    fecha: date | None = None,
    current_user: Usuario = Depends(get_current_user),
    service: CajaService = Depends(get_caja_service),
) -> CierreCajaResponse:
    fecha_consulta = fecha or date.today()
    return service.cerrar_caja(fecha_consulta, current_user.id)
