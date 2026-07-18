from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.inventario_repository import (
    ProveedorRepository,
    IngredienteRepository,
    MovimientoInventarioRepository,
    InsumoRepository,
    CategoriaInsumoRepository,
    UnidadMedidaRepository,
)
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
from app.services.gasto_service import GastoService


class InventarioService:
    """
    Servicio de lógica de negocio para el módulo de inventario.

    Coordina las operaciones de proveedores, ingredientes
    y movimientos de stock del restaurante.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.proveedor_repo = ProveedorRepository(db)
        self.ingrediente_repo = IngredienteRepository(db)
        self.movimiento_repo = MovimientoInventarioRepository(db)
        self.insumo_repo = InsumoRepository(db)
        self.categoria_insumo_repo = CategoriaInsumoRepository(db)
        self.unidad_medida_repo = UnidadMedidaRepository(db)
        self.gasto_service = GastoService(db)

    # =========================================================================
    # Movimientos de Inventario (Operación Principal)
    # =========================================================================

    def registrar_movimiento(
        self,
        movimiento_in: MovimientoCreate
    ) -> MovimientoResponse:
        """
        Registra un movimiento de inventario y actualiza el stock.

        Flujo:
        1. Actualiza el stock del ingrediente (valida existencia y stock suficiente).
        2. Registra el movimiento en la base de datos.
        3. Retorna el movimiento creado.

        Args:
            movimiento_in: Datos del movimiento a registrar.

        Returns:
            MovimientoResponse con el movimiento registrado.

        Raises:
            HTTPException 404: Si el ingrediente no existe.
            HTTPException 400: Si no hay stock suficiente para una salida.
        """
        try:
            insumo = self.insumo_repo.actualizar_stock(
                insumo_id=movimiento_in.insumo_id,
                cantidad=movimiento_in.cantidad,
                tipo_movimiento=movimiento_in.tipo
            )
        except ValueError as e:
            if "No se encontró" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e)
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        movimiento_data = movimiento_in.model_dump()
        movimiento_creado = self.movimiento_repo.create(movimiento_data)

        if movimiento_in.tipo == "SALIDA":
            insumo_obj = self.insumo_repo.get_by_id(movimiento_in.insumo_id)
            costo = Decimal(str(movimiento_in.cantidad)) * Decimal(str(insumo_obj.costo_unitario))
            if costo > 0:
                self.gasto_service.registrar_gasto_automatico(
                    insumo_id=movimiento_in.insumo_id,
                    concepto=f"SALIDA inventario: {insumo_obj.nombre} — {movimiento_in.motivo}",
                    monto=costo,
                )

        return MovimientoResponse.model_validate(movimiento_creado)

    # =========================================================================
    # Alertas de Reabastecimiento
    # =========================================================================

    def obtener_alertas_reabastecimiento(self) -> List[IngredienteResponse]:
        """
        Obtiene la lista de ingredientes por debajo del stock mínimo.

        Returns:
            Lista de IngredienteResponse con los ingredientes críticos.
        """
        ingredientes = self.ingrediente_repo.get_bajo_stock_minimo()
        return [IngredienteResponse.model_validate(i) for i in ingredientes]

    # =========================================================================
    # Proveedores
    # =========================================================================

    def crear_proveedor(
        self,
        proveedor_in: ProveedorCreate
    ) -> ProveedorResponse:
        """
        Crea un nuevo proveedor.

        Args:
            proveedor_in: Datos del proveedor a crear.

        Returns:
            ProveedorResponse con el proveedor creado.
        """
        proveedor_data = proveedor_in.model_dump()
        proveedor_creado = self.proveedor_repo.create(proveedor_data)
        return ProveedorResponse.model_validate(proveedor_creado)

    def obtener_proveedor(self, proveedor_id: int) -> ProveedorResponse:
        """
        Obtiene un proveedor por su ID.

        Args:
            proveedor_id: ID del proveedor.

        Returns:
            ProveedorResponse con los datos del proveedor.

        Raises:
            HTTPException 404: Si el proveedor no existe.
        """
        proveedor = self.proveedor_repo.get_by_id(proveedor_id)
        if not proveedor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el proveedor con ID {proveedor_id}"
            )
        return ProveedorResponse.model_validate(proveedor)

    def listar_proveedores(self) -> List[ProveedorResponse]:
        """
        Lista todos los proveedores registrados.

        Returns:
            Lista de ProveedorResponse.
        """
        proveedores = self.proveedor_repo.get_all()
        return [ProveedorResponse.model_validate(p) for p in proveedores]

    # =========================================================================
    # Ingredientes
    # =========================================================================

    def crear_ingrediente(
        self,
        ingrediente_in: IngredienteCreate
    ) -> IngredienteResponse:
        """
        Crea un nuevo ingrediente.

        Args:
            ingrediente_in: Datos del ingrediente a crear.

        Returns:
            IngredienteResponse con el ingrediente creado.

        Raises:
            HTTPException 404: Si el proveedor_id no existe.
            HTTPException 400: Si ya existe un ingrediente con ese nombre.
        """
        if ingrediente_in.proveedor_id is not None:
            proveedor = self.proveedor_repo.get_by_id(
                ingrediente_in.proveedor_id
            )
            if not proveedor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"No se encontró el proveedor con ID "
                        f"{ingrediente_in.proveedor_id}"
                    )
                )

        ingredientes_existentes = self.ingrediente_repo.get_by_nombre(
            ingrediente_in.nombre
        )
        for existente in ingredientes_existentes:
            if existente.nombre.lower() == ingrediente_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Ya existe un ingrediente con el nombre "
                        f"'{ingrediente_in.nombre}'"
                    )
                )

        ingrediente_data = ingrediente_in.model_dump()
        ingrediente_creado = self.ingrediente_repo.create(ingrediente_data)
        return IngredienteResponse.model_validate(ingrediente_creado)

    def obtener_ingrediente(self, ingrediente_id: int) -> IngredienteResponse:
        """
        Obtiene un ingrediente por su ID.

        Args:
            ingrediente_id: ID del ingrediente.

        Returns:
            IngredienteResponse con los datos del ingrediente.

        Raises:
            HTTPException 404: Si el ingrediente no existe.
        """
        ingrediente = self.ingrediente_repo.get_by_id(ingrediente_id)
        if not ingrediente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el ingrediente con ID {ingrediente_id}"
            )
        return IngredienteResponse.model_validate(ingrediente)

    def listar_ingredientes(self) -> List[IngredienteResponse]:
        """
        Lista todos los ingredientes registrados.

        Returns:
            Lista de IngredienteResponse.
        """
        ingredientes = self.ingrediente_repo.get_all()
        return [IngredienteResponse.model_validate(i) for i in ingredientes]

    # =========================================================================
    # Historial de Movimientos
    # =========================================================================

    def historial_movimientos(
        self,
        insumo_id: int
    ) -> List[MovimientoResponse]:
        """
        Obtiene el historial de movimientos de un insumo.

        Args:
            insumo_id: ID del insumo.

        Returns:
            Lista de MovimientoResponse ordenada por fecha descendente.

        Raises:
            HTTPException 404: Si el insumo no existe.
        """
        insumo = self.insumo_repo.get_by_id(insumo_id)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el insumo con ID {insumo_id}"
            )

        movimientos = self.movimiento_repo.get_by_insumo(insumo_id)
        return [MovimientoResponse.model_validate(m) for m in movimientos]

    # =========================================================================
    # Insumos
    # =========================================================================

    def crear_insumo(
        self,
        insumo_in: InsumoCreate
    ) -> InsumoResponse:
        """
        Crea un nuevo insumo en el inventario.

        Args:
            insumo_in: Datos del insumo a crear.

        Returns:
            InsumoResponse con el insumo creado.

        Raises:
            HTTPException 400: Si ya existe un insumo con ese nombre.
        """
        insumos_existentes = self.insumo_repo.get_by_nombre(insumo_in.nombre)
        for existente in insumos_existentes:
            if existente.nombre.lower() == insumo_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Ya existe un insumo con el nombre "
                        f"'{insumo_in.nombre}'"
                    )
                )

        insumo_data = insumo_in.model_dump()
        insumo_creado = self.insumo_repo.create(insumo_data)
        return InsumoResponse.model_validate(insumo_creado)

    def obtener_insumo(self, insumo_id: int) -> InsumoResponse:
        """
        Obtiene un insumo por su ID.

        Args:
            insumo_id: ID del insumo.

        Returns:
            InsumoResponse con los datos del insumo.

        Raises:
            HTTPException 404: Si el insumo no existe.
        """
        insumo = self.insumo_repo.get_by_id(insumo_id)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el insumo con ID {insumo_id}"
            )
        return InsumoResponse.model_validate(insumo)

    def listar_insumos(self) -> List[InsumoResponse]:
        """
        Lista todos los insumos registrados.

        Returns:
            Lista de InsumoResponse.
        """
        insumos = self.insumo_repo.get_all()
        return [InsumoResponse.model_validate(i) for i in insumos]

    def actualizar_stock_insumo(
        self,
        insumo_id: int,
        datos: ActualizarStockInsumo
    ) -> InsumoResponse:
        """
        Actualiza el stock de un insumo (entrada o salida).

        Args:
            insumo_id: ID del insumo.
            datos: Datos del ajuste de stock.

        Returns:
            InsumoResponse con el insumo actualizado.

        Raises:
            HTTPException 404: Si el insumo no existe.
            HTTPException 400: Si no hay stock suficiente para una salida.
        """
        try:
            insumo = self.insumo_repo.actualizar_stock(
                insumo_id=insumo_id,
                cantidad=datos.cantidad,
                tipo_movimiento=datos.tipo
            )
        except ValueError as e:
            if "No se encontró" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e)
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        return InsumoResponse.model_validate(insumo)

    def alertas_insumos(self) -> List[InsumoResponse]:
        """
        Obtiene insumos por debajo del stock mínimo.

        Returns:
            Lista de InsumoResponse con insumos en nivel crítico.
        """
        insumos = self.insumo_repo.get_bajo_stock_minimo()
        return [InsumoResponse.model_validate(i) for i in insumos]

    def actualizar_insumo(
        self, insumo_id: int, datos: InsumoUpdate
    ) -> InsumoResponse:
        """
        Actualiza detalles de un insumo (categoría, unidad, stock_mínimo).

        Args:
            insumo_id: ID del insumo.
            datos: Campos a actualizar (parcial).

        Returns:
            InsumoResponse con el insumo actualizado.

        Raises:
            HTTPException 404: Si el insumo no existe.
        """
        insumo = self.insumo_repo.get_by_id(insumo_id)
        if not insumo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el insumo con ID {insumo_id}"
            )
        update_data = datos.model_dump(exclude_unset=True)
        if update_data:
            self.insumo_repo.update(insumo_id, update_data)
            insumo = self.insumo_repo.get_by_id(insumo_id)
        return InsumoResponse.model_validate(insumo)

    # =========================================================================
    # Categorías de Insumo
    # =========================================================================

    def crear_categoria_insumo(self, data: CategoriaInsumoCreate) -> CategoriaInsumoResponse:
        existing = self.categoria_insumo_repo.get_all()
        for c in existing:
            if c.nombre.lower() == data.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una categoría con el nombre '{data.nombre}'"
                )
        cat = self.categoria_insumo_repo.create({"nombre": data.nombre})
        return CategoriaInsumoResponse.model_validate(cat)

    def listar_categorias_insumo(self) -> List[CategoriaInsumoResponse]:
        cats = self.categoria_insumo_repo.get_all(order_by="nombre")
        return [CategoriaInsumoResponse.model_validate(c) for c in cats]

    def eliminar_categoria_insumo(self, cat_id: int) -> None:
        cat = self.categoria_insumo_repo.get_by_id(cat_id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la categoría con ID {cat_id}"
            )
        count = self.categoria_insumo_repo.contar_insumos_por_categoria(cat_id)
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar '{cat.nombre}': tiene {count} insumo(s) asociado(s). Reasigna o elimina los insumos primero."
            )
        self.categoria_insumo_repo.delete(cat_id)

    # =========================================================================
    # Unidades de Medida
    # =========================================================================

    def crear_unidad_medida(self, data: UnidadMedidaCreate) -> UnidadMedidaResponse:
        existing = self.unidad_medida_repo.get_all()
        for u in existing:
            if u.nombre.lower() == data.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una unidad con el nombre '{data.nombre}'"
                )
            if u.abreviatura.lower() == data.abreviatura.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una unidad con la abreviatura '{data.abreviatura}'"
                )
        unidad = self.unidad_medida_repo.create({"nombre": data.nombre, "abreviatura": data.abreviatura})
        return UnidadMedidaResponse.model_validate(unidad)

    def listar_unidades_medida(self) -> List[UnidadMedidaResponse]:
        units = self.unidad_medida_repo.get_all(order_by="nombre")
        return [UnidadMedidaResponse.model_validate(u) for u in units]

    def eliminar_unidad_medida(self, unidad_id: int) -> None:
        unidad = self.unidad_medida_repo.get_by_id(unidad_id)
        if not unidad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la unidad de medida con ID {unidad_id}"
            )
        count = self.unidad_medida_repo.contar_insumos_por_unidad(unidad_id)
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar '{unidad.nombre}': tiene {count} insumo(s) asociado(s). Reasigna o elimina los insumos primero."
            )
        self.unidad_medida_repo.delete(unidad_id)
