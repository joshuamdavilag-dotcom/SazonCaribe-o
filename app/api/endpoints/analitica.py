from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import requerir_rol
from app.schemas.analitica import CierreCajaResponse
from app.schemas.personal import RolEnum
from app.services.analitica_service import AnaliticaService

router = APIRouter()


def get_analitica_service(db: Session = Depends(get_db)) -> AnaliticaService:
    return AnaliticaService(db)


@router.get(
    "/cierre-caja",
    response_model=CierreCajaResponse,
    summary="Obtener cierre de caja",
    description="Retorna las métricas financieras del día: total vendido, órdenes pagadas/canceladas y producto estrella.",
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def cierre_caja(
    fecha: Optional[date] = Query(
        default=None,
        description="Fecha del cierre (formato YYYY-MM-DD). Si se omite, usa la fecha actual."
    ),
    service: AnaliticaService = Depends(get_analitica_service)
) -> CierreCajaResponse:
    fecha_consulta = fecha if fecha else date.today()
    return service.obtener_cierre_caja(fecha_consulta)
