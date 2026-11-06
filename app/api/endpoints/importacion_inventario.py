"""Endpoints de importación inteligente de inventario."""

from typing import List

from fastapi import APIRouter, Depends, File, Path, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, requerir_permiso
from app.core.database import get_db
from app.models.personal import Usuario
from app.schemas.importacion_inventario import (
    ImportacionAplicarRequest,
    ImportacionAplicarResponse,
    ImportacionInventarioResponse,
    ImportacionInventarioResumenResponse,
)
from app.services.importacion_inventario_service import ImportacionInventarioService


router = APIRouter(
    dependencies=[Depends(requerir_permiso("inventario_gestionar"))]
)


def get_importacion_service(
    db: Session = Depends(get_db),
) -> ImportacionInventarioService:
    """Retorna el servicio de importación ligado a la sesión de BD."""
    return ImportacionInventarioService(db)


@router.post(
    "/importaciones/analizar",
    response_model=ImportacionInventarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analizar un archivo de inventario",
    description=(
        "Lee un archivo Excel, CSV, TXT, PDF o DOCX, detecta los artículos, "
        "cantidades, precios y empaques, y deja el lote en revisión. "
        "No escribe nada en el inventario hasta aplicar el lote."
    ),
)
async def analizar_importacion(
    archivo: UploadFile = File(
        ...,
        description="Archivo de inventario (xlsx, xlsm, csv, txt, pdf, docx)",
    ),
    current_user: Usuario = Depends(get_current_user),
    service: ImportacionInventarioService = Depends(get_importacion_service),
) -> ImportacionInventarioResponse:
    contenido = await archivo.read()
    return service.analizar(archivo.filename or "archivo", contenido, current_user)


@router.get(
    "/importaciones/",
    response_model=List[ImportacionInventarioResumenResponse],
    summary="Listar importaciones recientes",
)
def listar_importaciones(
    service: ImportacionInventarioService = Depends(get_importacion_service),
) -> List[ImportacionInventarioResumenResponse]:
    return service.listar()


@router.get(
    "/importaciones/{importacion_id}",
    response_model=ImportacionInventarioResponse,
    summary="Obtener una importación con sus filas",
)
def obtener_importacion(
    importacion_id: int = Path(..., gt=0),
    service: ImportacionInventarioService = Depends(get_importacion_service),
) -> ImportacionInventarioResponse:
    return service.obtener(importacion_id)


@router.post(
    "/importaciones/{importacion_id}/aplicar",
    response_model=ImportacionAplicarResponse,
    summary="Aplicar el lote revisado al inventario",
    description=(
        "Valida el lote completo, crea o actualiza los insumos y registra "
        "los movimientos de ENTRADA en una sola transacción."
    ),
)
def aplicar_importacion(
    payload: ImportacionAplicarRequest,
    importacion_id: int = Path(..., gt=0),
    current_user: Usuario = Depends(get_current_user),
    service: ImportacionInventarioService = Depends(get_importacion_service),
) -> ImportacionAplicarResponse:
    return service.aplicar(importacion_id, payload, current_user)


@router.delete(
    "/importaciones/{importacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Descartar una importación en revisión",
)
def eliminar_importacion(
    importacion_id: int = Path(..., gt=0),
    service: ImportacionInventarioService = Depends(get_importacion_service),
) -> None:
    service.eliminar(importacion_id)
