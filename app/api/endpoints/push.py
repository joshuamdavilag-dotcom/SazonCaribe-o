from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.vapid import claves_vapid
from app.models.personal import Usuario
from app.schemas.push import (
    PushConfigResponse,
    PushDesuscripcionRequest,
    PushPreferenciasResponse,
    PushPreferenciasUpdate,
    PushSuscripcionCreate,
    PushSuscripcionResponse,
)
from app.services.push_service import (
    PUSH_DISPONIBLE,
    PushService,
    aplicar_preferencias_avisos,
)

router = APIRouter()


def get_push_service(db: Session = Depends(get_db)) -> PushService:
    """Retorna el servicio de push ligado a la sesión de BD de la petición."""
    return PushService(db)


def _preferencias(usuario: Usuario) -> PushPreferenciasResponse:
    """Serializa las preferencias de avisos del usuario."""
    return PushPreferenciasResponse(
        avisos_fuera_de_turno=bool(usuario.avisos_fuera_de_turno),
        avisos_cocina=bool(usuario.avisos_cocina),
        avisos_mesero=bool(usuario.avisos_mesero),
        avisos_mesero_todas=bool(usuario.avisos_mesero_todas),
    )


@router.get(
    "/config",
    response_model=PushConfigResponse,
    summary="Configuración de Web Push",
    description=(
        "Devuelve la clave pública VAPID que el navegador usa para suscribirse "
        "y si el servicio de push está habilitado en el servidor."
    ),
    dependencies=[Depends(get_current_user)],
)
def obtener_config_push(
    current_user: Usuario = Depends(get_current_user),
) -> PushConfigResponse:
    """Devuelve la clave pública VAPID y el estado del servicio de push."""
    publica, privada = claves_vapid()
    habilitado = bool(publica and privada and PUSH_DISPONIBLE)
    return PushConfigResponse(
        public_key=publica if habilitado else None,
        habilitado=habilitado,
        vapid_subject=get_settings().VAPID_SUBJECT,
        avisos_fuera_de_turno=bool(current_user.avisos_fuera_de_turno),
        avisos_cocina=bool(current_user.avisos_cocina),
        avisos_mesero=bool(current_user.avisos_mesero),
        avisos_mesero_todas=bool(current_user.avisos_mesero_todas),
    )


@router.get(
    "/preferencias",
    response_model=PushPreferenciasResponse,
    summary="Preferencias de avisos push del usuario",
    description=(
        "Indica qué avisos recibe el usuario: comandas nuevas (cocina), sus "
        "propias comandas listas (mesero), las de otros meseros y si los "
        "recibe también fuera del sistema."
    ),
    dependencies=[Depends(get_current_user)],
)
def obtener_preferencias_push(
    current_user: Usuario = Depends(get_current_user),
) -> PushPreferenciasResponse:
    """Devuelve las preferencias de avisos push del usuario actual."""
    return _preferencias(current_user)


@router.patch(
    "/preferencias",
    response_model=PushPreferenciasResponse,
    summary="Actualizar preferencias de avisos push",
    description=(
        "Activa o desactiva por separado los avisos de cocina, los de mesero "
        "y los de todas las comandas, además de la entrega fuera del sistema. "
        "Los campos omitidos conservan su valor actual."
    ),
    dependencies=[Depends(get_current_user)],
)
def actualizar_preferencias_push(
    body: PushPreferenciasUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> PushPreferenciasResponse:
    """Guarda las preferencias de avisos push del usuario actual."""
    aplicar_preferencias_avisos(current_user, body)
    db.commit()
    db.refresh(current_user)
    return _preferencias(current_user)


@router.post(
    "/subscribe",
    response_model=PushSuscripcionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar dispositivo para notificaciones push",
    description=(
        "Guarda la suscripción Web Push del dispositivo. Si el endpoint ya "
        "existe, se actualiza para el usuario actual."
    ),
    dependencies=[Depends(get_current_user)],
)
def suscribir_push(
    body: PushSuscripcionCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    service: PushService = Depends(get_push_service),
) -> PushSuscripcionResponse:
    """Registra el dispositivo del usuario para recibir notificaciones push."""
    suscripcion = service.registrar_suscripcion(
        current_user,
        body.endpoint,
        body.keys.p256dh,
        body.keys.auth,
        request.headers.get("user-agent"),
    )
    return PushSuscripcionResponse.model_validate(suscripcion)


@router.post(
    "/unsubscribe",
    summary="Dar de baja un dispositivo",
    description="Elimina la suscripción Web Push del dispositivo indicado.",
    dependencies=[Depends(get_current_user)],
)
def desuscribir_push(
    body: PushDesuscripcionRequest,
    current_user: Usuario = Depends(get_current_user),
    service: PushService = Depends(get_push_service),
) -> dict:
    """Elimina la suscripción del dispositivo del usuario actual."""
    eliminada = service.eliminar_suscripcion(current_user, body.endpoint)
    return {"eliminada": eliminada}


@router.get(
    "/subscriptions",
    response_model=List[PushSuscripcionResponse],
    summary="Dispositivos registrados del usuario",
    description="Lista los dispositivos con notificaciones push activas.",
    dependencies=[Depends(get_current_user)],
)
def listar_suscripciones_push(
    current_user: Usuario = Depends(get_current_user),
    service: PushService = Depends(get_push_service),
) -> List[PushSuscripcionResponse]:
    """Lista los dispositivos suscritos por el usuario actual."""
    return [
        PushSuscripcionResponse.model_validate(suscripcion)
        for suscripcion in service.listar_suscripciones(current_user)
    ]


@router.delete(
    "/subscriptions/{suscripcion_id}",
    summary="Eliminar un dispositivo registrado",
    description="Elimina una suscripción push propia por su identificador.",
    dependencies=[Depends(get_current_user)],
)
def eliminar_suscripcion_push(
    suscripcion_id: int,
    current_user: Usuario = Depends(get_current_user),
    service: PushService = Depends(get_push_service),
) -> dict:
    """Elimina una suscripción del usuario actual."""
    eliminada = service.eliminar_suscripcion_por_id(current_user, suscripcion_id)
    if not eliminada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La suscripción no existe o no pertenece al usuario",
        )
    return {"eliminada": eliminada}
