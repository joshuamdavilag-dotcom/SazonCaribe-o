from typing import List, Optional

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.menu_publico import (
    CategoriaMenuPublicaResponse,
    MenuItemPublicoResponse,
)
from app.services.menu_service import MenuService

router = APIRouter()


def get_menu_service(db: Session = Depends(get_db)) -> MenuService:
    """
    Dependencia para inyectar el servicio de menú en los endpoints públicos.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de MenuService.
    """
    return MenuService(db)


# =============================================================================
# Endpoints públicos de solo lectura (futura Carta Digital)
# =============================================================================
# NOTA: No requieren autenticación y nunca exponen costos, inventario interno,
# recetas, usuarios ni roles.

@router.get(
    "/menu",
    response_model=List[MenuItemPublicoResponse],
    summary="Obtener carta pública",
    description=(
        "Lista todos los platos disponibles del menú para la carta digital. "
        "Solo lectura: no incluye recetas, costos ni inventario interno."
    ),
)
def obtener_menu_publico(
    service: MenuService = Depends(get_menu_service),
) -> List[MenuItemPublicoResponse]:
    """
    Retorna la lista de platos disponibles (disponible=True).
    """
    return service.obtener_menu_publico()


@router.get(
    "/categories",
    response_model=List[CategoriaMenuPublicaResponse],
    summary="Obtener categorías públicas",
    description=(
        "Lista las categorías del menú para la carta digital. "
        "Solo lectura: expone únicamente id, nombre y descripción."
    ),
)
def obtener_categorias_publicas(
    service: MenuService = Depends(get_menu_service),
) -> List[CategoriaMenuPublicaResponse]:
    """
    Retorna la lista completa de categorías del menú.
    """
    return service.obtener_categorias_publicas()


@router.get(
    "/menu/{categoria_id}",
    response_model=List[MenuItemPublicoResponse],
    summary="Obtener carta pública por categoría",
    description=(
        "Lista los platos disponibles de una categoría específica para la "
        "carta digital. Solo lectura."
    ),
)
def obtener_menu_por_categoria(
    categoria_id: int = Path(
        ...,
        gt=0,
        description="ID de la categoría del menú"
    ),
    service: MenuService = Depends(get_menu_service),
) -> List[MenuItemPublicoResponse]:
    """
    Retorna los platos disponibles de la categoría indicada.
    """
    return service.obtener_menu_publico(categoria_id)


@router.get(
    "/item/{item_id}",
    response_model=MenuItemPublicoResponse,
    summary="Obtener plato público por ID",
    description=(
        "Obtiene un plato disponible del menú por su ID para la carta digital. "
        "Solo lectura."
    ),
)
def obtener_item_publico(
    item_id: int = Path(
        ...,
        gt=0,
        description="ID del plato"
    ),
    service: MenuService = Depends(get_menu_service),
) -> MenuItemPublicoResponse:
    """
    Retorna los datos de exhibición del plato indicado.

    Devuelve 404 si el plato no existe o no está disponible.
    """
    return service.obtener_item_publico_por_id(item_id)
