from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import requerir_rol
from app.schemas.personal import RolEnum
from app.schemas.menu import (
    CategoriaMenuCreate,
    CategoriaMenuResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate
)
from app.services.menu_service import MenuService

router = APIRouter()

# Dependencia de RBAC para endpoints de escritura en menú
_requerir_rol_menu = Depends(
    requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE])
)


def get_menu_service(db: Session = Depends(get_db)) -> MenuService:
    """
    Dependencia para inyectar el servicio de menú.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de MenuService.
    """
    return MenuService(db)


# =============================================================================
# Endpoints de Categorías
# =============================================================================

@router.post(
    "/categorias",
    response_model=CategoriaMenuResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría del menú",
    description="Registra una nueva categoría en el menú (ej: Entradas, Postres).",
    tags=["Menú y Recetas"],
    dependencies=[_requerir_rol_menu]
)
def crear_categoria(
    categoria_in: CategoriaMenuCreate,
    service: MenuService = Depends(get_menu_service)
) -> CategoriaMenuResponse:
    """
    Crea una nueva categoría del menú.

    - **nombre**: Nombre único de la categoría (requerido)
    - **descripcion**: Descripción opcional de la categoría
    """
    return service.crear_categoria(categoria_in)


@router.get(
    "/categorias",
    response_model=List[CategoriaMenuResponse],
    summary="Listar categorías del menú",
    description="Obtiene todas las categorías registradas en el menú.",
    tags=["Menú y Recetas"]
)
def listar_categorias(
    service: MenuService = Depends(get_menu_service)
) -> List[CategoriaMenuResponse]:
    """
    Retorna la lista completa de categorías del menú.
    """
    return service.obtener_categorias()


@router.delete(
    "/categorias/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar categoría del menú",
    description="Elimina una categoría que no tenga platillos asociados.",
    tags=["Menú y Recetas"],
    dependencies=[_requerir_rol_menu]
)
def eliminar_categoria(
    categoria_id: int = Path(
        ...,
        gt=0,
        description="ID de la categoría a eliminar"
    ),
    service: MenuService = Depends(get_menu_service)
) -> None:
    """
    Elimina una categoría del menú.

    No se puede eliminar si tiene platillos asociados.
    """
    service.eliminar_categoria(categoria_id)


# =============================================================================
# Endpoints de Platos (MenuItems)
# =============================================================================

@router.post(
    "/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear plato del menú",
    description="Registra un nuevo plato en el menú con su receta opcional.",
    tags=["Menú y Recetas"],
    dependencies=[_requerir_rol_menu]
)
def crear_menu_item(
    item_in: MenuItemCreate,
    service: MenuService = Depends(get_menu_service)
) -> MenuItemResponse:
    """
    Crea un nuevo plato en el menú.

    - **nombre**: Nombre único del plato (requerido)
    - **descripcion**: Descripción del plato
    - **precio**: Precio de venta al cliente (requerido, > 0)
    - **disponible**: Disponibilidad en el menú (default: True)
    - **categoria_id**: ID de la categoría (requerido)
    - **ingredientes_receta**: Lista opcional de ingredientes del plato

    El sistema valida:
    - Que la categoría exista
    - Que cada ingrediente exista en inventario
    - Que el nombre del plato sea único
    """
    return service.crear_menu_item(item_in)


@router.get(
    "/items",
    response_model=List[MenuItemResponse],
    summary="Listar platos del menú",
    description="Obtiene todos los platos del menú, opcionalmente filtrados por categoría.",
    tags=["Menú y Recetas"]
)
def listar_menu_items(
    categoria_id: Optional[int] = Query(
        default=None,
        gt=0,
        description="Filtrar por ID de categoría (opcional)"
    ),
    service: MenuService = Depends(get_menu_service)
) -> List[MenuItemResponse]:
    """
    Retorna la lista de platos del menú.

    - **categoria_id**: Si se proporciona, filtra por esta categoría

    Cada plato incluye:
    - Datos básicos (nombre, precio, disponibilidad)
    - Categoría asociada
    - Lista de ingredientes de su receta
    """
    return service.obtener_items(categoria_id)


@router.get(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Obtener plato por ID",
    description="Obtiene los datos de un plato específico con su receta.",
    tags=["Menú y Recetas"]
)
def obtener_menu_item(
    item_id: int = Path(
        ...,
        gt=0,
        description="ID del plato"
    ),
    service: MenuService = Depends(get_menu_service)
) -> MenuItemResponse:
    """
    Retorna los datos del plato con el ID especificado.
    """
    return service.obtener_item_por_id(item_id)


@router.put(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Actualizar plato del menú",
    description=(
        "Actualiza los datos de un plato existente. "
        "Permite modificar nombre, precio, categoría, disponibilidad "
        "y la lista completa de ingredientes de la receta."
    ),
    tags=["Menú y Recetas"],
    dependencies=[_requerir_rol_menu]
)
def actualizar_menu_item(
    item_in: MenuItemUpdate,
    item_id: int = Path(
        ...,
        gt=0,
        description="ID del plato a actualizar"
    ),
    service: MenuService = Depends(get_menu_service)
) -> MenuItemResponse:
    """
    Actualiza un plato del menú (parcial).

    Todos los campos son opcionales. Solo se actualizan los enviados.

    - **nombre**: Nuevo nombre (debe ser único)
    - **descripcion**: Nueva descripción
    - **precio**: Nuevo precio
    - **disponible**: Disponibilidad
    - **categoria_id**: Nueva categoría
    - **ingredientes_receta**: Nueva lista de ingredientes (reemplaza la existente)

    El sistema valida:
    - Que el plato exista
    - Que la categoría nueva exista (si se cambia)
    - Que cada ingrediente nuevo exista (si se cambia la receta)
    - Que el nombre sea único entre platos
    """
    return service.actualizar_menu_item(item_id, item_in)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar plato del menú",
    description="Elimina un plato y sus recetas asociadas. Solo administradores.",
    tags=["Menú y Recetas"],
    dependencies=[_requerir_rol_menu]
)
def eliminar_menu_item(
    item_id: int = Path(..., gt=0, description="ID del plato a eliminar"),
    service: MenuService = Depends(get_menu_service)
) -> None:
    service.eliminar_platillo(item_id)
