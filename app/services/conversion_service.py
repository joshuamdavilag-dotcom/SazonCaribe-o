from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventario import UnidadMedida


def _get_chain(db: Session, unidad_id: int) -> Optional[dict]:
    """
    Resolve a unit to its root base and accumulate the total factor.

    Returns {"base_id": int, "factor": float} or None if the unit
    has no base (it IS the base, or is isolated).
    """
    visited = set()
    current_id = unidad_id
    total_factor = 1.0

    while current_id is not None:
        if current_id in visited:
            return None
        visited.add(current_id)

        unidad = db.get(UnidadMedida, current_id)
        if unidad is None:
            return None

        if unidad.unidad_base_id is None:
            return {"base_id": current_id, "factor": total_factor}

        total_factor *= (unidad.factor_conversion or 1.0)
        current_id = unidad.unidad_base_id

    return None


def convertir_cantidad(
    db: Session,
    cantidad: float,
    unidad_origen_id: int,
    unidad_destino_id: int,
) -> float:
    """
    Convierte una cantidad de una unidad a otra.

    Ambas unidades deben compartir la misma unidad base (directa o
    transitivamente). Si no son compatibles, lanza HTTPException 400.

    Args:
        db: Sesión de base de datos.
        cantidad: Cantidad a convertir (debe ser > 0).
        unidad_origen_id: ID de la unidad de origen.
        unidad_destino_id: ID de la unidad de destino.

    Returns:
        Cantidad convertida en la unidad destino.

    Raises:
        HTTPException 404: Si alguna unidad no existe.
        HTTPException 400: Si las unidades no son compatibles.
    """
    if unidad_origen_id == unidad_destino_id:
        return cantidad

    origen = db.get(UnidadMedida, unidad_origen_id)
    if not origen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la unidad de origen con ID {unidad_origen_id}"
        )

    destino = db.get(UnidadMedida, unidad_destino_id)
    if not destino:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la unidad de destino con ID {unidad_destino_id}"
        )

    chain_origen = _get_chain(db, unidad_origen_id)
    chain_destino = _get_chain(db, unidad_destino_id)

    if not chain_origen or not chain_destino:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una o ambas unidades no tienen una unidad base definida para conversión"
        )

    if chain_origen["base_id"] != chain_destino["base_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Las unidades '{origen.nombre}' y '{destino.nombre}' "
                f"no son compatibles (magnitudes diferentes)"
            )
        )

    factor_origen = chain_origen["factor"]
    factor_destino = chain_destino["factor"]

    return cantidad * factor_origen / factor_destino
