from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.novedad import NovedadesListaResponse
from app.services.novedad_service import NovedadService

router = APIRouter()


def get_novedad_service(db: Session = Depends(get_db)) -> NovedadService:
    """Retorna el servicio de novedades ligado a la sesión de BD de la petición."""
    return NovedadService(db)


@router.get(
    "/",
    response_model=NovedadesListaResponse,
    summary="Listar novedades del sistema",
    description="Historial de actualizaciones publicadas, más reciente primero.",
    tags=["Novedades"],
    dependencies=[Depends(get_current_user)],
)
def listar_novedades(
    limite: int = Query(default=30, ge=1, le=100),
    service: NovedadService = Depends(get_novedad_service),
) -> NovedadesListaResponse:
    """Devuelve las novedades publicadas y la última versión disponible."""
    novedades = service.listar(limite=limite)
    return NovedadesListaResponse(
        novedades=novedades,
        ultima_version=novedades[0].version if novedades else None,
    )
