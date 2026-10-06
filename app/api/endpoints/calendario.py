from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.calendario import CalendarioResponse, EventoCalendarioRequest, EventoCalendarioResponse
from app.schemas.personal import RolEnum
from app.services.calendario_service import CalendarioService

router = APIRouter()
_SOLO_GERENCIA = Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))


def _validar_rango(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise HTTPException(status_code=400, detail="La fecha inicial debe ser anterior o igual a la fecha final")
    if (hasta - desde).days > 62:
        raise HTTPException(status_code=400, detail="El rango del calendario no puede superar 63 días")


@router.get("/", response_model=CalendarioResponse)
def obtener_calendario(
    desde: date = Query(...),
    hasta: date = Query(...),
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validar_rango(desde, hasta)
    return CalendarioService(db).obtener_calendario(desde, hasta)


@router.post(
    "/eventos",
    response_model=EventoCalendarioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_SOLO_GERENCIA],
)
def crear_evento(
    datos: EventoCalendarioRequest,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CalendarioService(db)
    evento = service.crear_evento(datos, usuario.id)
    return next(
        item for item in service.obtener_calendario(evento.fecha_inicio, evento.fecha_inicio)["eventos"]
        if item["id"] == evento.id
    )


@router.put(
    "/eventos/{evento_id}",
    response_model=EventoCalendarioResponse,
    dependencies=[_SOLO_GERENCIA],
)
def actualizar_evento(
    evento_id: int,
    datos: EventoCalendarioRequest,
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CalendarioService(db)
    evento = service.actualizar_evento(evento_id, datos)
    return next(
        item for item in service.obtener_calendario(evento.fecha_inicio, evento.fecha_inicio)["eventos"]
        if item["id"] == evento.id
    )


@router.delete(
    "/eventos/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_SOLO_GERENCIA],
)
def eliminar_evento(
    evento_id: int,
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    CalendarioService(db).eliminar_evento(evento_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
