"""Endpoints del módulo de correos."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_permiso
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.correo import (
    ConfiguracionCorreoResponse,
    ConfiguracionCorreoUpdate,
    CorreoEnviarRequest,
    CorreoPruebaRequest,
    CorreoVistaPreviaRequest,
    CorreoVistaPreviaResponse,
    DestinatarioCorreoCreate,
    DestinatarioCorreoResponse,
    DestinatarioCorreoUpdate,
    EnvioCorreoResponse,
    EstadoCorreosResponse,
)
from app.services.correo_service import CorreoService

router = APIRouter()


def get_correo_service(db: Session = Depends(get_db)) -> CorreoService:
    """Servicio de correos ligado a la sesión de la petición."""
    return CorreoService(db)


@router.get(
    "/estado",
    response_model=EstadoCorreosResponse,
    summary="Estado del módulo de correos",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def estado_correos(servicio: CorreoService = Depends(get_correo_service)):
    """Indica si Brevo está configurado y resume la cola de envíos."""
    return servicio.estado()


@router.get(
    "/catalogo",
    summary="Tipos de correo y secciones disponibles",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def catalogo_correos(servicio: CorreoService = Depends(get_correo_service)):
    """Configuración de todos los tipos de correo del sistema."""
    return servicio.listar_configuracion()


@router.get(
    "/destinatarios",
    response_model=list[DestinatarioCorreoResponse],
    summary="Lista de destinatarios de correo",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def listar_destinatarios(
    solo_activos: bool = False,
    servicio: CorreoService = Depends(get_correo_service),
):
    return servicio.listar_destinatarios(solo_activos=solo_activos)


@router.post(
    "/destinatarios",
    response_model=DestinatarioCorreoResponse,
    status_code=201,
    summary="Agregar destinatario",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def crear_destinatario(
    datos: DestinatarioCorreoCreate,
    servicio: CorreoService = Depends(get_correo_service),
):
    return servicio.crear_destinatario(datos)


@router.put(
    "/destinatarios/{destinatario_id}",
    response_model=DestinatarioCorreoResponse,
    summary="Editar destinatario",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def actualizar_destinatario(
    destinatario_id: int,
    datos: DestinatarioCorreoUpdate,
    servicio: CorreoService = Depends(get_correo_service),
):
    return servicio.actualizar_destinatario(destinatario_id, datos)


@router.delete(
    "/destinatarios/{destinatario_id}",
    status_code=204,
    summary="Eliminar destinatario",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def eliminar_destinatario(
    destinatario_id: int,
    servicio: CorreoService = Depends(get_correo_service),
):
    servicio.eliminar_destinatario(destinatario_id)


@router.get(
    "/configuracion",
    response_model=list[ConfiguracionCorreoResponse],
    summary="Configuración por tipo de correo",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def listar_configuracion(servicio: CorreoService = Depends(get_correo_service)):
    return servicio.listar_configuracion()


@router.put(
    "/configuracion/{tipo}",
    response_model=ConfiguracionCorreoResponse,
    summary="Guardar configuración de un tipo de correo",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def guardar_configuracion(
    tipo: str,
    datos: ConfiguracionCorreoUpdate,
    servicio: CorreoService = Depends(get_correo_service),
):
    return servicio.guardar_configuracion(tipo, datos)


@router.post(
    "/vista-previa",
    response_model=CorreoVistaPreviaResponse,
    summary="Vista previa del correo",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def vista_previa(
    datos: CorreoVistaPreviaRequest,
    servicio: CorreoService = Depends(get_correo_service),
):
    resolucion = servicio._resolver_envio(
        datos.tipo,
        datos.secciones,
        None,
        datos.desde,
        datos.hasta,
        None,
        None,
        usar_config=True,
    )
    return {
        "asunto": resolucion["asunto"],
        "html": resolucion["html"],
        "desde": resolucion["desde"],
        "hasta": resolucion["hasta"],
        "secciones": resolucion["secciones"],
    }


@router.post(
    "/enviar",
    response_model=EnvioCorreoResponse,
    summary="Enviar un correo ahora",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def enviar_correo(
    datos: CorreoEnviarRequest,
    servicio: CorreoService = Depends(get_correo_service),
    current_user: Usuario = Depends(get_current_user),
):
    return servicio.enviar_ahora(
        datos.tipo,
        datos.secciones,
        datos.destinatario_ids,
        datos.desde,
        datos.hasta,
        datos.asunto,
        actor_id=current_user.id,
    )


@router.post(
    "/probar",
    response_model=EnvioCorreoResponse,
    summary="Enviar un correo de prueba",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def probar_correo(
    datos: CorreoPruebaRequest,
    servicio: CorreoService = Depends(get_correo_service),
    current_user: Usuario = Depends(get_current_user),
):
    return servicio.enviar_prueba(datos.email, actor_id=current_user.id)


@router.get(
    "/historial",
    response_model=list[EnvioCorreoResponse],
    summary="Historial de envíos",
    dependencies=[Depends(requerir_permiso("correos_gestionar"))],
)
def historial_correos(
    limite: int = 50,
    servicio: CorreoService = Depends(get_correo_service),
):
    return servicio.historial(limite=max(1, min(limite, 200)))
