import json
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import requerir_rol, get_current_user
from app.models.personal import Usuario
from app.schemas.personal import RolEnum
from app.services.backup_service import backup_service
from app.services.auditoria_service import auditoria_service

router = APIRouter(
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR]))]
)


@router.post("/crear", status_code=status.HTTP_201_CREATED)
def crear_backup(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Crea una nueva copia de seguridad (Backup) en formato JSON estructurado.
    Solo accesible para el rol ADMINISTRADOR.
    """
    try:
        resultado = backup_service.crear_backup(db=db, usuario_id=current_user.id)
        return {
            "mensaje": "Copia de seguridad creada correctamente",
            "backup": resultado
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar la copia de seguridad: {str(e)}"
        )


@router.get("/", response_model=List[Dict[str, Any]])
def listar_backups() -> List[Dict[str, Any]]:
    """
    Lista todas las copias de seguridad guardadas en el servidor.
    Solo accesible para el rol ADMINISTRADOR.
    """
    return backup_service.listar_backups()


@router.get("/descargar/{filename}")
def descargar_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Descarga el archivo JSON de copia de seguridad indicado.
    Solo accesible para el rol ADMINISTRADOR.
    """
    filepath = backup_service.obtener_ruta_backup(filename)
    if not filepath:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo de copia de seguridad no existe o la ruta es inválida"
        )

    auditoria_service.log_evento(
        db=db,
        usuario_id=current_user.id,
        modulo="BACKUP",
        accion="DESCARGAR_BACKUP",
        detalles=f"Descargó la copia de seguridad '{filename}'"
    )

    return FileResponse(
        path=filepath,
        filename=filepath.name,
        media_type="application/json"
    )


@router.delete("/{filename}")
def eliminar_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Elimina una copia de seguridad almacenada en el servidor.
    Solo accesible para el rol ADMINISTRADOR.
    """
    exito = backup_service.eliminar_backup(filename=filename, db=db, usuario_id=current_user.id)
    if not exito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo no existe o no se pudo eliminar"
        )
    return {"mensaje": f"Copia de seguridad '{filename}' eliminada correctamente"}


@router.post("/subir-y-restaurar")
async def subir_y_restaurar_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Sube un archivo .json de copia de seguridad al servidor y registra el evento.
    Solo accesible para el rol ADMINISTRADOR.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos de copia de seguridad en formato .json"
        )

    try:
        content = await file.read()
        json_data = json.loads(content.decode("utf-8"))
        
        if "metadata" not in json_data or "datos" not in json_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo JSON no tiene la estructura válida de copia de seguridad de Sazón Caribeño"
            )

        filepath = backup_service.obtener_ruta_backup(file.filename) or (backup_service.BACKUP_DIR if hasattr(backup_service, "BACKUP_DIR") else backup_service._model_to_dict)
        from pathlib import Path
        dest_path = Path("app/backups") / file.filename
        with open(dest_path, "wb") as f:
            f.write(content)

        auditoria_service.log_evento(
            db=db,
            usuario_id=current_user.id,
            modulo="BACKUP",
            accion="SUBIR_BACKUP",
            detalles=f"Subió e importó el archivo de copia de seguridad '{file.filename}'"
        )

        return {
            "mensaje": f"Archivo '{file.filename}' subido y guardado exitosamente en el servidor",
            "registros_guardados": json_data.get("metadata", {}).get("total_registros", 0)
        }
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado no es un JSON válido"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar la copia de seguridad: {str(e)}"
        )
