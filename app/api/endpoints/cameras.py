from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.camera import (
    CameraAccessUpdate,
    CameraBridgeAuthorization,
    CameraClipCreate,
    CameraClipResponse,
    CameraCreate,
    CameraResponse,
    CameraStorageResponse,
    CameraStreamTokenResponse,
    CameraUpdate,
    CameraViewerResponse,
)
from app.schemas.personal import RolEnum
from app.services.camera_service import CameraService, CAMERA_CHUNK_MAX_BYTES

router = APIRouter()
_GESTORES = [RolEnum.ADMINISTRADOR, RolEnum.GERENTE]


def get_camera_service(db: Session = Depends(get_db)) -> CameraService:
    """Retorna el servicio de cámaras ligado a la sesión de BD de la petición."""
    return CameraService(db)


@router.post(
    "/authorize",
    status_code=status.HTTP_200_OK,
    summary="Autorizar un lector WebRTC del puente",
)
def autorizar_puente(
    datos: CameraBridgeAuthorization,
    service: CameraService = Depends(get_camera_service),
) -> dict[str, bool]:
    """Valida las credenciales del lector WebRTC del puente de cámaras."""
    token = datos.password or datos.token
    camera_slug = datos.user or datos.path
    service.autorizar_puente(camera_slug, token, datos.action, datos.path)
    return {"autorizado": True}


@router.get(
    "/eligible-users",
    response_model=List[CameraViewerResponse],
    dependencies=[Depends(requerir_rol(_GESTORES))],
)
def listar_usuarios_autorizables(
    service: CameraService = Depends(get_camera_service),
) -> list[dict]:
    """Lista los usuarios que pueden recibir acceso a las cámaras."""
    return service.listar_usuarios_autorizables()


@router.get(
    "/storage",
    response_model=CameraStorageResponse,
    dependencies=[Depends(requerir_rol(_GESTORES))],
)
def resumen_almacenamiento(
    service: CameraService = Depends(get_camera_service),
) -> dict[str, int]:
    """Devuelve el resumen de almacenamiento usado por los clips de video."""
    return service.resumen_almacenamiento()


@router.get("/clips", response_model=List[CameraClipResponse])
def listar_clips(
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> list[dict]:
    """Lista los clips de video visibles para el usuario logueado."""
    return service.listar_clips(current_user)


@router.get("/clips/{clip_id}/video")
def descargar_video_clip(
    clip_id: str,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> FileResponse:
    """Descarga el archivo de video de un clip autorizado."""
    path, mime_type = service.obtener_video_clip(clip_id, current_user)
    return FileResponse(
        path,
        media_type=mime_type,
        filename=path.name,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_clip(
    clip_id: str,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> Response:
    """Elimina un clip de video cancelando su grabación y archivo."""
    service.cancelar_clip(clip_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=List[CameraResponse])
def listar_camaras(
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> list[dict]:
    """Lista las cámaras visibles para el usuario logueado."""
    return service.listar_camaras(current_user)


@router.post(
    "/",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requerir_rol(_GESTORES))],
)
def crear_camara(
    datos: CameraCreate,
    service: CameraService = Depends(get_camera_service),
) -> dict:
    """Registra una nueva cámara en el sistema."""
    return service.crear_camara(datos)


@router.patch(
    "/{camera_id}",
    response_model=CameraResponse,
    dependencies=[Depends(requerir_rol(_GESTORES))],
)
def actualizar_camara(
    camera_id: int,
    datos: CameraUpdate,
    service: CameraService = Depends(get_camera_service),
) -> dict:
    """Actualiza los datos de una cámara existente."""
    return service.actualizar_camara(camera_id, datos)


@router.put(
    "/{camera_id}/access",
    response_model=CameraResponse,
    dependencies=[Depends(requerir_rol(_GESTORES))],
)
def actualizar_accesos(
    camera_id: int,
    datos: CameraAccessUpdate,
    service: CameraService = Depends(get_camera_service),
) -> dict:
    """Actualiza los permisos de acceso de una cámara."""
    return service.actualizar_accesos(camera_id, datos)


@router.post(
    "/{camera_id}/stream-token",
    response_model=CameraStreamTokenResponse,
)
def emitir_token_stream(
    camera_id: int,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> dict:
    """Emite un token temporal de acceso al stream de una cámara."""
    return service.emitir_token_stream(camera_id, current_user)


@router.post(
    "/{camera_id}/clips",
    status_code=status.HTTP_201_CREATED,
)
def iniciar_clip(
    camera_id: int,
    datos: CameraClipCreate,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> dict[str, str]:
    """Inicia la grabación de un nuevo clip de video para una cámara."""
    return service.iniciar_clip(camera_id, current_user, datos.mime_type)


@router.put("/{camera_id}/clips/{clip_id}/chunks/{sequence}")
async def guardar_fragmento(
    camera_id: int,
    clip_id: str,
    sequence: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> dict[str, int]:
    """Guarda un fragmento (chunk) del video de un clip en curso."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Content-Length inválido"
            ) from exc
        if declared_length > CAMERA_CHUNK_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail="El fragmento supera el máximo de 16 MiB",
            )
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > CAMERA_CHUNK_MAX_BYTES:
            raise HTTPException(status_code=413, detail="El fragmento supera el máximo de 16 MiB")
    return service.guardar_fragmento(
        camera_id, clip_id, sequence, current_user, bytes(data)
    )


@router.post("/{camera_id}/clips/{clip_id}/finish", response_model=CameraClipResponse)
def finalizar_clip(
    camera_id: int,
    clip_id: str,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> dict:
    """Finaliza la grabación de un clip y consolida sus fragmentos."""
    return service.finalizar_clip(camera_id, clip_id, current_user)


@router.delete(
    "/{camera_id}/clips/{clip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancelar_clip(
    camera_id: int,
    clip_id: str,
    current_user: Usuario = Depends(get_current_user),
    service: CameraService = Depends(get_camera_service),
) -> Response:
    """Cancela la grabación de un clip de video de una cámara."""
    service.cancelar_clip(clip_id, current_user, camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
