from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.gasto import (
    GastoCreate,
    GastoUpdate,
    GastoEliminarRequest,
    GastoResponse,
)
from app.schemas.personal import RolEnum
from app.services.gasto_service import GastoService

router = APIRouter()


def get_gasto_service(db: Session = Depends(get_db)) -> GastoService:
    """Retorna el servicio de gastos ligado a la sesión de BD de la petición."""
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
    """Registra un gasto operativo del restaurante a nombre del usuario logueado."""
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
    """Lista los gastos, opcionalmente filtrados por rango de fechas."""
    return service.listar_gastos(fecha_inicio, fecha_fin)


@router.put(
    "/{gasto_id}",
    response_model=GastoResponse,
    summary="Editar gasto operativo",
    description=(
        "Modifica un gasto existente. Requiere `motivo` obligatorio; "
        "el estado anterior y el nuevo quedan en la bitácora de auditoría."
    ),
    tags=["Gastos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def editar_gasto(
    gasto_id: int,
    gasto_in: GastoUpdate,
    current_user: Usuario = Depends(get_current_user),
    service: GastoService = Depends(get_gasto_service),
) -> GastoResponse:
    """Edita un gasto operativo dejando rastro en auditoría."""
    return service.editar_gasto(gasto_id, gasto_in, current_user)


@router.delete(
    "/{gasto_id}",
    response_model=GastoResponse,
    summary="Eliminar gasto operativo",
    description=(
        "Elimina (borrado lógico) un gasto. Requiere `motivo` obligatorio; "
        "el gasto deja de contar en totales pero queda registrado en auditoría."
    ),
    tags=["Gastos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def eliminar_gasto(
    gasto_id: int,
    body: GastoEliminarRequest,
    current_user: Usuario = Depends(get_current_user),
    service: GastoService = Depends(get_gasto_service),
) -> GastoResponse:
    """Elimina lógicamente un gasto operativo con motivo obligatorio."""
    return service.eliminar_gasto(gasto_id, body.motivo, current_user)