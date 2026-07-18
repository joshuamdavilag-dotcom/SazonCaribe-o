from typing import List

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import requerir_rol
from app.schemas.personal import RolEnum
from app.schemas.inventario import (
    ProveedorCreate,
    ProveedorResponse,
    IngredienteCreate,
    IngredienteResponse,
    MovimientoCreate,
    MovimientoResponse,
    InsumoCreate,
    InsumoResponse,
    InsumoUpdate,
    ActualizarStockInsumo,
    CategoriaInsumoCreate,
    CategoriaInsumoResponse,
    UnidadMedidaCreate,
    UnidadMedidaResponse,
)
from app.services.inventario_service import InventarioService

router = APIRouter()

# Dependencia de RBAC para endpoints de escritura en inventario
_requerir_rol_inventario = Depends(
    requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE])
)


def get_inventario_service(db: Session = Depends(get_db)) -> InventarioService:
    """
    Dependencia para inyectar el servicio de inventario.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de InventarioService.
    """
    return InventarioService(db)


# =============================================================================
# Endpoints de Proveedores
# =============================================================================

@router.post(
    "/proveedores",
    response_model=ProveedorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
    description="Registra un nuevo proveedor en el sistema.",
    tags=["Inventario & Proveedores"],
    dependencies=[_requerir_rol_inventario]
)
def crear_proveedor(
    proveedor_in: ProveedorCreate,
    service: InventarioService = Depends(get_inventario_service)
) -> ProveedorResponse:
    """
    Crea un nuevo proveedor para el restaurante.

    - **nombre**: Nombre del proveedor (requerido)
    - **contacto_nombre**: Nombre del vendedor o contacto directo
    - **telefono**: Número de teléfono
    - **email**: Correo electrónico
    """
    return service.crear_proveedor(proveedor_in)


@router.get(
    "/proveedores",
    response_model=List[ProveedorResponse],
    summary="Listar proveedores",
    description="Obtiene la lista de todos los proveedores registrados.",
    tags=["Inventario & Proveedores"]
)
def listar_proveedores(
    service: InventarioService = Depends(get_inventario_service)
) -> List[ProveedorResponse]:
    """
    Retorna la lista completa de proveedores del restaurante.
    """
    return service.listar_proveedores()


# =============================================================================
# Endpoints de Ingredientes
# =============================================================================

@router.post(
    "/ingredientes",
    response_model=IngredienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear ingrediente",
    description="Registra un nuevo ingrediente en el inventario.",
    tags=["Inventario & Proveedores"],
    dependencies=[_requerir_rol_inventario]
)
def crear_ingrediente(
    ingrediente_in: IngredienteCreate,
    service: InventarioService = Depends(get_inventario_service)
) -> IngredienteResponse:
    """
    Crea un nuevo ingrediente en el inventario.

    - **nombre**: Nombre único del ingrediente (requerido)
    - **unidad_medida**: Unidad de medida (Kg, Litros, Unidades, etc.)
    - **stock_minimo**: Stock mínimo para alertas (default: 5.00)
    - **proveedor_id**: ID del proveedor principal (opcional)

    El sistema valida que:
    - El nombre sea único en el sistema
    - El proveedor_id exista (si se proporciona)
    """
    return service.crear_ingrediente(ingrediente_in)


@router.get(
    "/ingredientes",
    response_model=List[IngredienteResponse],
    summary="Listar ingredientes",
    description="Obtiene la lista de todos los ingredientes en inventario.",
    tags=["Inventario & Proveedores"]
)
def listar_ingredientes(
    service: InventarioService = Depends(get_inventario_service)
) -> List[IngredienteResponse]:
    """
    Retorna la lista completa de ingredientes del restaurante.
    """
    return service.listar_ingredientes()


@router.get(
    "/ingredientes/alertas",
    response_model=List[IngredienteResponse],
    summary="Alertas de reabastecimiento",
    description="Obtiene ingredientes por debajo del stock mínimo.",
    tags=["Inventario & Proveedores"]
)
def obtener_alertas(
    service: InventarioService = Depends(get_inventario_service)
) -> List[IngredienteResponse]:
    """
    Retorna ingredientes con stock_actual <= stock_minimo.
    """
    return service.obtener_alertas_reabastecimiento()


# =============================================================================
# Endpoints de Movimientos
# =============================================================================

@router.post(
    "/movimientos",
    response_model=MovimientoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar movimiento de inventario",
    description="Registra una entrada o salida de stock de un ingrediente.",
    tags=["Inventario & Proveedores"],
    dependencies=[_requerir_rol_inventario]
)
def registrar_movimiento(
    movimiento_in: MovimientoCreate,
    service: InventarioService = Depends(get_inventario_service)
) -> MovimientoResponse:
    """
    Registra un movimiento de inventario (entrada o salida).

    - **insumo_id**: ID del insumo
    - **tipo**: "ENTRADA" o "SALIDA" (requerido)
    - **cantidad**: Cantidad a mover (debe ser > 0)
    - **motivo**: Motivo del movimiento

    El sistema:
    1. Actualiza el stock del insumo automáticamente
    2. Valida stock suficiente para salidas
    3. Registra el movimiento en el historial
    """
    return service.registrar_movimiento(movimiento_in)


# =============================================================================
# Endpoints de Consulta
# =============================================================================

@router.get(
    "/ingredientes/{ingrediente_id}/historial",
    response_model=List[MovimientoResponse],
    summary="Historial de movimientos",
    description="Obtiene el historial completo de movimientos de un ingrediente.",
    tags=["Inventario & Proveedores"]
)
def historial_movimientos(
    ingrediente_id: int = Path(
        ...,
        gt=0,
        description="ID del ingrediente"
    ),
    service: InventarioService = Depends(get_inventario_service)
) -> List[MovimientoResponse]:
    """
    Retorna el historial completo de movimientos de un ingrediente.
    """
    return service.historial_movimientos(ingrediente_id)


# =============================================================================
# Endpoints de Insumos
# =============================================================================

@router.get(
    "/insumos",
    response_model=List[InsumoResponse],
    summary="Listar insumos",
    description="Obtiene la lista de todos los insumos del inventario.",
    tags=["Inventario"]
)
def listar_insumos(
    service: InventarioService = Depends(get_inventario_service)
) -> List[InsumoResponse]:
    """
    Retorna la lista completa de insumos registrados.
    """
    return service.listar_insumos()


@router.get(
    "/insumos/alertas",
    response_model=List[InsumoResponse],
    summary="Alertas de stock bajo en insumos",
    description="Obtiene insumos por debajo del stock mínimo.",
    tags=["Inventario"]
)
def alertas_insumos(
    service: InventarioService = Depends(get_inventario_service)
) -> List[InsumoResponse]:
    """
    Retorna insumos con cantidad_actual <= stock_minimo.
    """
    return service.alertas_insumos()


@router.get(
    "/insumos/{insumo_id}",
    response_model=InsumoResponse,
    summary="Obtener insumo por ID",
    description="Obtiene los datos de un insumo específico.",
    tags=["Inventario"]
)
def obtener_insumo(
    insumo_id: int = Path(
        ...,
        gt=0,
        description="ID del insumo"
    ),
    service: InventarioService = Depends(get_inventario_service)
) -> InsumoResponse:
    """
    Retorna los datos del insumo con el ID especificado.
    """
    return service.obtener_insumo(insumo_id)


@router.post(
    "/insumos",
    response_model=InsumoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear insumo",
    description="Registra un nuevo insumo en el inventario.",
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario]
)
def crear_insumo(
    insumo_in: InsumoCreate,
    service: InventarioService = Depends(get_inventario_service)
) -> InsumoResponse:
    """
    Crea un nuevo insumo en el inventario.

    - **nombre**: Nombre único del insumo (requerido)
    - **cantidad_actual**: Stock inicial (default: 0)
    - **unidad_medida**: Unidad de medida (requerido)
    - **stock_minimo**: Stock mínimo para alertas (default: 5)
    """
    return service.crear_insumo(insumo_in)


@router.patch(
    "/insumos/{insumo_id}/stock",
    response_model=InsumoResponse,
    summary="Actualizar stock de un insumo",
    description=(
        "Ajusta el stock de un insumo: ENTRADA suma, SALIDA resta. "
        "Registra el motivo del cambio."
    ),
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario]
)
def actualizar_stock_insumo(
    insumo_id: int = Path(
        ...,
        gt=0,
        description="ID del insumo"
    ),
    datos: ActualizarStockInsumo = ...,
    service: InventarioService = Depends(get_inventario_service)
) -> InsumoResponse:
    """
    Actualiza el stock de un insumo.

    - **tipo**: "ENTRADA" (llega proveedor) o "SALIDA" (se consume)
    - **cantidad**: Cantidad a agregar o restar (debe ser > 0)
    - **motivo**: Descripción del movimiento

    El sistema valida stock suficiente para salidas y crea
    un registro de movimiento en el historial.
    """
    return service.actualizar_stock_insumo(insumo_id, datos)


@router.patch(
    "/insumos/{insumo_id}",
    response_model=InsumoResponse,
    summary="Actualizar detalles de un insumo",
    description=(
        "Actualiza categoría, unidad de medida o stock mínimo de un insumo."
    ),
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario]
)
def actualizar_insumo(
    insumo_id: int = Path(
        ..., gt=0, description="ID del insumo"
    ),
    datos: InsumoUpdate = ...,
    service: InventarioService = Depends(get_inventario_service)
) -> InsumoResponse:
    return service.actualizar_insumo(insumo_id, datos)


# =============================================================================
# Endpoints de Categorías de Insumo
# =============================================================================

@router.get(
    "/categorias-insumo",
    response_model=List[CategoriaInsumoResponse],
    summary="Listar categorías de insumo",
    tags=["Inventario"],
)
def listar_categorias_insumo(
    service: InventarioService = Depends(get_inventario_service),
) -> List[CategoriaInsumoResponse]:
    return service.listar_categorias_insumo()


@router.post(
    "/categorias-insumo",
    response_model=CategoriaInsumoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría de insumo",
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario],
)
def crear_categoria_insumo(
    data: CategoriaInsumoCreate,
    service: InventarioService = Depends(get_inventario_service),
) -> CategoriaInsumoResponse:
    return service.crear_categoria_insumo(data)


@router.delete(
    "/categorias-insumo/{cat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar categoría de insumo",
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario],
)
def eliminar_categoria_insumo(
    cat_id: int = Path(..., gt=0, description="ID de la categoría"),
    service: InventarioService = Depends(get_inventario_service),
):
    service.eliminar_categoria_insumo(cat_id)


# =============================================================================
# Endpoints de Unidades de Medida
# =============================================================================

@router.get(
    "/unidades-medida",
    response_model=List[UnidadMedidaResponse],
    summary="Listar unidades de medida",
    tags=["Inventario"],
)
def listar_unidades_medida(
    service: InventarioService = Depends(get_inventario_service),
) -> List[UnidadMedidaResponse]:
    return service.listar_unidades_medida()


@router.post(
    "/unidades-medida",
    response_model=UnidadMedidaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear unidad de medida",
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario],
)
def crear_unidad_medida(
    data: UnidadMedidaCreate,
    service: InventarioService = Depends(get_inventario_service),
) -> UnidadMedidaResponse:
    return service.crear_unidad_medida(data)


@router.delete(
    "/unidades-medida/{unidad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar unidad de medida",
    tags=["Inventario"],
    dependencies=[_requerir_rol_inventario],
)
def eliminar_unidad_medida(
    unidad_id: int = Path(..., gt=0, description="ID de la unidad"),
    service: InventarioService = Depends(get_inventario_service),
):
    service.eliminar_unidad_medida(unidad_id)
