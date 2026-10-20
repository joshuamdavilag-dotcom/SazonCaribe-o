from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import requerir_rol
from app.core.database import get_db
from app.schemas.descuento import (
    DescuentoFrecuenteCreate,
    DescuentoFrecuenteUpdate,
    DescuentoFrecuenteResponse,
)
from app.schemas.personal import RolEnum
from app.services.descuento_service import DescuentoFrecuenteService

router = APIRouter()


def get_descuento_service(db: Session = Depends(get_db)) -> DescuentoFrecuenteService:
    return DescuentoFrecuenteService(db)


@router.get(
    "/",
    response_model=List[DescuentoFrecuenteResponse],
    summary="Listar descuentos predeterminados",
    description="Lista el catálogo de descuentos frecuentes. Con solo_activos=true devuelve únicamente los disponibles para aplicar.",
    tags=["Descuentos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE, RolEnum.VENDEDOR]))],
)
def listar_descuentos(
    solo_activos: bool = Query(default=False),
    service: DescuentoFrecuenteService = Depends(get_descuento_service),
) -> List[DescuentoFrecuenteResponse]:
    return service.listar(solo_activos=solo_activos)


@router.post(
    "/",
    response_model=DescuentoFrecuenteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear descuento predeterminado",
    description="Crea un descuento reutilizable (porcentaje o monto fijo) para el catálogo.",
    tags=["Descuentos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def crear_descuento(
    data_in: DescuentoFrecuenteCreate,
    service: DescuentoFrecuenteService = Depends(get_descuento_service),
) -> DescuentoFrecuenteResponse:
    return service.crear(data_in)


@router.put(
    "/{descuento_id}",
    response_model=DescuentoFrecuenteResponse,
    summary="Actualizar descuento predeterminado",
    description="Actualiza nombre, tipo, valor o disponibilidad de un descuento del catálogo.",
    tags=["Descuentos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def actualizar_descuento(
    descuento_id: int,
    data_in: DescuentoFrecuenteUpdate,
    service: DescuentoFrecuenteService = Depends(get_descuento_service),
) -> DescuentoFrecuenteResponse:
    return service.actualizar(descuento_id, data_in)


@router.delete(
    "/{descuento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar descuento predeterminado",
    description="Elimina un descuento del catálogo.",
    tags=["Descuentos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))],
)
def eliminar_descuento(
    descuento_id: int,
    service: DescuentoFrecuenteService = Depends(get_descuento_service),
) -> None:
    service.eliminar(descuento_id)
