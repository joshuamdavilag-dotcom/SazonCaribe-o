from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.gasto import GastoCreate, GastoResponse
from app.schemas.personal import RolEnum
from app.services.gasto_service import GastoService

router = APIRouter()


def get_gasto_service(db: Session = Depends(get_db)) -> GastoService:
    return GastoService(db)


@router.post(
    "/",
    response_model=GastoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar gasto operativo",
    description="Registra un gasto operativo del restaurante.",
    tags=["Gastos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def crear_gasto(
    gasto_in: GastoCreate,
    current_user: Usuario = Depends(get_current_user),
    service: GastoService = Depends(get_gasto_service),
) -> GastoResponse:
    return service.registrar_gasto(gasto_in, current_user.id)


@router.get(
    "/",
    response_model=List[GastoResponse],
    summary="Listar gastos",
    description="Lista gastos, con filtro opcional por rango de fechas.",
    tags=["Gastos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def listar_gastos(
    fecha_inicio: Optional[date] = Query(default=None),
    fecha_fin: Optional[date] = Query(default=None),
    service: GastoService = Depends(get_gasto_service),
) -> List[GastoResponse]:
    return service.listar_gastos(fecha_inicio, fecha_fin)
