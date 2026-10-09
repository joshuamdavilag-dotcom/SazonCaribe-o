from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.auditoria import AuditoriaPageResponse
from app.schemas.personal import RolEnum
from app.services.auditoria_service import AuditoriaService

router = APIRouter()


@router.get(
    "/",
    response_model=AuditoriaPageResponse,
    summary="Consultar bitácora de auditoría",
)
def listar_registros_auditoria(
    desde: date | None = None,
    hasta: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditoriaPageResponse:
    if current_user.rol not in (RolEnum.ADMINISTRADOR.value, RolEnum.GERENTE.value):
        raise HTTPException(
            status_code=403,
            detail="Solo administradores y gerentes pueden consultar la bitácora",
        )
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=400,
            detail="La fecha inicial no puede ser posterior a la fecha final",
        )
    return AuditoriaService(db).listar(desde, hasta, limit, offset)