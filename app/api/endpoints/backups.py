import json
from types import SimpleNamespace
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import requerir_permiso, get_current_user
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.services.backup_service import backup_service
from app.services.auditoria_service import AuditoriaService

router = APIRouter(
    dependencies=[Depends(requerir_permiso("backups_gestionar"))]
)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


@router.post("/crear", status_code=status.HTTP_201_CREATED)
def crear_backup(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """Crea una copia de seguridad manual y la guarda en la base de datos.

    Solo accesible para el rol ADMINISTRADOR.
    """
    try:
        resultado = backup_service.crear_backup_bd(
            db=db, actor=current_user, origen="manual"
        )
        return {
            "mensaje": "Copia de seguridad creada correctamente",
            "backup": resultado,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar la copia de seguridad: {str(e)}",
        )


@router.get("/", response_model=List[Dict[str, Any]])
def listar_backups(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Lista las copias guardadas (sin el contenido). Solo ADMINISTRADOR."""
    return backup_service.listar_backups_bd(db)


@router.get("/estado")
def estado_backups(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Última copia y fecha de la próxima copia automática."""
    return backup_service.estado(db)


@router.get("/descargar/{backup_id}")
def descargar_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Descarga el JSON de una copia. Solo ADMINISTRADOR."""
    registro = backup_service.obtener_backup_bd(db, backup_id)
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La copia de seguridad no existe",
        )

    AuditoriaService.registrar(
        db=db,
        actor=current_user,
        accion="DESCARGAR_BACKUP",
        entidad_tipo="BACKUP",
        entidad_id=registro.id,
        descripcion=f"Descargó la copia de seguridad '{registro.nombre}'",
    )
    db.commit()

    return Response(
        content=registro.contenido,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{registro.nombre}"'
        },
    )


@router.delete("/{backup_id}")
def eliminar_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, str]:
    """Elimina una copia guardada. Solo ADMINISTRADOR."""
    exito = backup_service.eliminar_backup_bd(db, backup_id, actor=current_user)
    if not exito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La copia de seguridad no existe",
        )
    return {"mensaje": "Copia de seguridad eliminada correctamente"}


@router.post("/subir-y-restaurar")
async def subir_y_restaurar_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """Sube un JSON de copia y restaura sus datos reemplazando los actuales.

    Solo accesible para el rol ADMINISTRADOR.
    """
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos de copia de seguridad en formato .json",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 100 MB",
        )

    try:
        json_data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado no es un JSON válido",
        )

    if not isinstance(json_data, dict) or "metadata" not in json_data or "datos" not in json_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El archivo JSON no tiene la estructura válida de copia de "
                "seguridad de Sazón Caribeño"
            ),
        )

    actor_id = current_user.id
    actor_username = current_user.username
    actor_rol = current_user.rol

    try:
        resultado = backup_service.restaurar_backup_bd(db, json_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al restaurar la copia de seguridad: {str(e)}",
        )

    # La restauración pudo reemplazar la fila del usuario actual: se usa una
    # instantánea para registrar la auditoría sin volver a consultar la BD.
    actor = SimpleNamespace(
        id=actor_id, username=actor_username, rol=actor_rol
    )
    try:
        AuditoriaService.registrar(
            db=db,
            actor=actor,
            accion="RESTAURAR_BACKUP",
            entidad_tipo="BACKUP",
            entidad_id=None,
            descripcion=(
                f"Restauró la copia '{file.filename}' "
                f"({resultado['tablas']} tablas, {resultado['registros']} registros)"
            ),
        )
        db.commit()
    except Exception:
        db.rollback()

    return {
        "mensaje": f"Copia '{file.filename}' restaurada correctamente",
        "tablas": resultado["tablas"],
        "registros": resultado["registros"],
        "fecha_backup": resultado["fecha_backup"],
    }
