"""Endpoints del Estudio de Mercado con IA (solo Administrador y Gerente)."""

import logging
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_rol
from app.core.database import get_db
from app.models.estudio_mercado import EstadoEstudio, TipoEstudio
from app.models.personal import Usuario
from app.schemas.estudio_mercado import (
    ConsultaEstudioRequest,
    ConsultaEstudioResponse,
    DocumentoEstudioResponse,
    EstudioMercadoResponse,
    GenerarEstudioRequest,
    MensajeEstudioResponse,
)
from app.schemas.personal import RolEnum
from app.services.estudio_mercado_service import EstudioMercadoService
from app.services.push_service import PushService

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)


def get_estudio_service(db: Session = Depends(get_db)) -> EstudioMercadoService:
    """Retorna el servicio de estudio de mercado ligado a la sesión de BD."""
    return EstudioMercadoService(db)


def ejecutar_generacion_estudio(estudio_id: int) -> None:
    """Tarea en segundo plano: genera el estudio y avisa a administración."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        servicio = EstudioMercadoService(db)
        estudio = servicio.generar(estudio_id)
        if estudio is None or estudio.notificado:
            return
        push = PushService(db)
        if estudio.estado == EstadoEstudio.COMPLETADO:
            push.notificar_estudio_mercado(estudio)
            estudio.notificado = True
            db.commit()
        elif estudio.estado == EstadoEstudio.ERROR and (estudio.intentos or 0) >= 1:
            push.notificar_estudio_mercado_error(estudio)
            estudio.notificado = True
            db.commit()
    except Exception:
        logger.exception("[ESTUDIO] Falló la generación en segundo plano del estudio %s", estudio_id)
    finally:
        db.close()


@router.post(
    "/generar",
    response_model=EstudioMercadoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generar estudio de mercado",
    description=(
        "Encola un estudio de mercado para el periodo indicado (día, semana, "
        "mes o año). La generación corre en segundo plano; consulta el "
        "estudio por su ID hasta que el estado sea COMPLETADO."
    ),
    tags=["Estudio de Mercado"],
)
def generar_estudio(
    background_tasks: BackgroundTasks,
    body: GenerarEstudioRequest,
    current_user: Usuario = Depends(get_current_user),
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> EstudioMercadoResponse:
    """Crea el estudio y lanza el análisis con IA en segundo plano."""
    estudio = service.iniciar_generacion(body.periodo, TipoEstudio.MANUAL, current_user)
    if estudio.estado == EstadoEstudio.GENERANDO:
        background_tasks.add_task(ejecutar_generacion_estudio, estudio.id)
    return estudio


@router.get(
    "/",
    response_model=List[EstudioMercadoResponse],
    summary="Listar estudios de mercado",
    tags=["Estudio de Mercado"],
)
def listar_estudios(
    limite: int = Query(default=30, ge=1, le=100),
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> List[EstudioMercadoResponse]:
    """Devuelve los estudios más recientes, automáticos y manuales."""
    return service.repo.listar_estudios(limite=limite)


# --------------------------------------------------------------------- #
#  Documentos (declarados antes de /{estudio_id} para no colisionar)
# --------------------------------------------------------------------- #

@router.post(
    "/documentos",
    response_model=DocumentoEstudioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir documento para el análisis",
    description=(
        "Recibe un PDF, DOCX, XLSX, CSV o TXT, extrae su texto y lo deja "
        "disponible para el análisis y para las consultas del asesor."
    ),
    tags=["Estudio de Mercado"],
)
async def subir_documento(
    archivo: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> DocumentoEstudioResponse:
    """Extrae y guarda el texto del documento subido."""
    contenido = await archivo.read()
    return service.subir_documento(
        nombre=archivo.filename or "documento",
        contenido=contenido,
        mime=archivo.content_type,
        usuario=current_user,
    )


@router.get(
    "/documentos",
    response_model=List[DocumentoEstudioResponse],
    summary="Listar documentos cargados",
    tags=["Estudio de Mercado"],
)
def listar_documentos(
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> List[DocumentoEstudioResponse]:
    """Devuelve los documentos disponibles para el análisis."""
    return service.repo.listar_documentos()


@router.delete(
    "/documentos/{documento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un documento",
    tags=["Estudio de Mercado"],
)
def eliminar_documento(
    documento_id: int,
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> None:
    """Borra un documento cargado y su texto extraído."""
    documento = service.repo.obtener_documento(documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="El documento no existe.")
    service.repo.eliminar_documento(documento)


# --------------------------------------------------------------------- #
#  Chat de asesoría
# --------------------------------------------------------------------- #

@router.post(
    "/chat",
    response_model=ConsultaEstudioResponse,
    summary="Consultar al asesor de IA",
    description=(
        "Responde únicamente consultas sobre el negocio o sobre el uso del "
        "sistema. Cualquier otro tema se rechaza sin responderlo."
    ),
    tags=["Estudio de Mercado"],
)
def consultar_asesor(
    body: ConsultaEstudioRequest,
    current_user: Usuario = Depends(get_current_user),
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> ConsultaEstudioResponse:
    """Aplica el filtro de alcance y genera la respuesta del asesor."""
    return service.responder(body.mensaje, current_user, body.documento_id)


@router.get(
    "/chat/historial",
    response_model=List[MensajeEstudioResponse],
    summary="Historial del chat de asesoría",
    tags=["Estudio de Mercado"],
)
def historial_chat(
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> List[MensajeEstudioResponse]:
    """Devuelve los últimos mensajes intercambiados con el asesor."""
    return service.repo.listar_mensajes()


@router.delete(
    "/chat/historial",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Limpiar el historial del chat",
    tags=["Estudio de Mercado"],
)
def limpiar_chat(
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> None:
    """Borra todos los mensajes del chat de asesoría."""
    service.repo.limpiar_mensajes()


@router.get(
    "/{estudio_id}",
    response_model=EstudioMercadoResponse,
    summary="Consultar un estudio de mercado",
    tags=["Estudio de Mercado"],
)
def obtener_estudio(
    estudio_id: int,
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> EstudioMercadoResponse:
    """Devuelve el estudio con su análisis y métricas."""
    estudio = service.repo.obtener_estudio(estudio_id)
    if estudio is None:
        raise HTTPException(status_code=404, detail="El estudio no existe.")
    return estudio


@router.delete(
    "/{estudio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un estudio de mercado",
    tags=["Estudio de Mercado"],
)
def eliminar_estudio(
    estudio_id: int,
    service: EstudioMercadoService = Depends(get_estudio_service),
) -> None:
    """Elimina un estudio generado."""
    estudio = service.repo.obtener_estudio(estudio_id)
    if estudio is None:
        raise HTTPException(status_code=404, detail="El estudio no existe.")
    service.repo.eliminar_estudio(estudio)
