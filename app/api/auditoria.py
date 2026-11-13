from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.core.permisos import tiene_permiso
from app.models.personal import Usuario
from app.schemas.auditoria import (
    AuditoriaPageResponse,
    EliminarAuditoriaRequest,
    EliminarAuditoriaResponse,
)
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
    """Lista la bitácora de auditoría paginada, solo para administradores y gerentes."""
    if not tiene_permiso(current_user, "auditoria_ver"):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para consultar la bitácora de auditoría",
        )
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=400,
            detail="La fecha inicial no puede ser posterior a la fecha final",
        )
    return AuditoriaService(db).listar(desde, hasta, limit, offset)


@router.delete(
    "/{registro_id}",
    response_model=EliminarAuditoriaResponse,
    summary="Eliminar un registro de la bitácora",
    description=(
        "Borra físicamente un registro de auditoría. Requiere `motivo` "
        "obligatorio y solo lo puede hacer un Administrador. La baja queda "
        "registrada como `AUDITORIA_ELIMINADA`, guardando solo la cabecera del "
        "registro borrado (fecha, actor, acción y entidad), sin su contenido."
    ),
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR]))],
)
def eliminar_registro_auditoria(
    registro_id: int = Path(..., gt=0, description="ID del registro de auditoría"),
    body: EliminarAuditoriaRequest = ...,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EliminarAuditoriaResponse:
    """Elimina un registro de la bitácora dejando rastro de quién lo borró."""
    return AuditoriaService(db).eliminar_registro(registro_id, body.motivo, current_user)
