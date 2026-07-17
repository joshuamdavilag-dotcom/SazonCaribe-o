from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.menu_repository import MenuRepository
from app.repositories.inventario_repository import InsumoRepository
from app.schemas.menu import (
    CategoriaMenuCreate,
    CategoriaMenuResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate
)


class MenuService:
    """
    Servicio de lógica de negocio para el módulo de menú.

    Coordina las operaciones de categorías, platos y recetas,
    validando la existencia de ingredientes en inventario.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.menu_repo = MenuRepository(db)
        self.insumo_repo = InsumoRepository(db)

    # =========================================================================
    # Categorías
    # =========================================================================

    def crear_categoria(
        self,
        categoria_in: CategoriaMenuCreate
    ) -> CategoriaMenuResponse:
        """
        Crea una nueva categoría del menú.

        Args:
            categoria_in: Datos de la categoría a crear.

        Returns:
            CategoriaMenuResponse con la categoría creada.

        Raises:
            HTTPException 400: Si ya existe una categoría con ese nombre.
        """
        categorias = self.menu_repo.obtener_categorias()
        for cat in categorias:
            if cat.nombre.lower() == categoria_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una categoría con el nombre '{categoria_in.nombre}'"
                )

        categoria_creada = self.menu_repo.crear_categoria(categoria_in)
        return CategoriaMenuResponse.model_validate(categoria_creada)

    def obtener_categorias(self) -> List[CategoriaMenuResponse]:
        """
        Lista todas las categorías del menú.

        Returns:
            Lista de CategoriaMenuResponse.
        """
        categorias = self.menu_repo.obtener_categorias()
        return [CategoriaMenuResponse.model_validate(c) for c in categorias]

    def eliminar_categoria(self, categoria_id: int) -> None:
        categoria = self.menu_repo.obtener_categoria_por_id(categoria_id)
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la categoría con ID {categoria_id}"
            )
        count = self.menu_repo.contar_items_por_categoria(categoria_id)
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar la categoría '{categoria.nombre}': tiene {count} platillo(s) asociado(s). Reasigna o elimina los platillos primero."
            )
        self.menu_repo.eliminar_categoria(categoria_id)

    # =========================================================================
    # Platos y Recetas
    # =========================================================================

    def crear_menu_item(
        self,
        item_in: MenuItemCreate
    ) -> MenuItemResponse:
        """
        Crea un nuevo plato en el menú con su receta.

        Flujo de validación:
        1. Verifica que la categoría exista.
        2. Si tiene ingredientes, verifica que cada uno exista en inventario.
        3. Si todo es válido, crea el plato con su receta.

        Args:
            item_in: Datos del plato y su receta (opcional).

        Returns:
            MenuItemResponse con el plato creado.

        Raises:
            HTTPException 404: Si la categoría o algún ingrediente no existe.
            HTTPException 400: Si ya existe un plato con ese nombre.
        """
        from app.models.menu import CategoriaMenu
        from sqlalchemy import select

        statement = select(CategoriaMenu).where(
            CategoriaMenu.id == item_in.categoria_id
        )
        categoria = self.db.execute(statement).scalar_one_or_none()

        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la categoría con ID {item_in.categoria_id}"
            )

        if item_in.receta:
            for receta in item_in.receta:
                insumo = self.insumo_repo.get_by_id(
                    receta.insumo_id
                )
                if not insumo:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"El insumo con ID {receta.insumo_id} "
                            f"no existe en el inventario"
                        )
                    )

        items_existentes = self.menu_repo.obtener_items()
        for item in items_existentes:
            if item.nombre.lower() == item_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un plato con el nombre '{item_in.nombre}'"
                )

        item_creado = self.menu_repo.crear_menu_item(item_in)
        return MenuItemResponse.model_validate(item_creado)

    def obtener_items(
        self,
        categoria_id: Optional[int] = None
    ) -> List[MenuItemResponse]:
        """
        Obtiene los platos del menú.

        Args:
            categoria_id: Si se proporciona, filtra por esta categoría.

        Returns:
            Lista de MenuItemResponse con sus recetas e ingredientes.
        """
        items = self.menu_repo.obtener_items(categoria_id)
        return [MenuItemResponse.model_validate(i) for i in items]

    def obtener_item_por_id(self, item_id: int) -> MenuItemResponse:
        """
        Obtiene un plato del menú por su ID.

        Args:
            item_id: ID del plato.

        Returns:
            MenuItemResponse con el plato y sus relaciones.

        Raises:
            HTTPException 404: Si el plato no existe.
        """
        item = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )
        return MenuItemResponse.model_validate(item)

    def actualizar_menu_item(
        self,
        item_id: int,
        item_in: MenuItemUpdate
    ) -> MenuItemResponse:
        """
        Actualiza un plato del menú con datos parciales.

        Flujo de validación:
        1. Verifica que el plato exista.
        2. Si se cambia la categoría, verifica que la nueva exista.
        3. Si se cambia la receta, verifica que cada ingrediente exista.
        4. Verifica unicidad del nombre si se está cambiando.

        Args:
            item_id: ID del plato a actualizar.
            item_in: Datos parciales a actualizar.

        Returns:
            MenuItemResponse con el plato actualizado.

        Raises:
            HTTPException 404: Si el plato, categoría o ingrediente no existe.
            HTTPException 400: Si el nombre ya está en uso por otro plato.
        """
        existing = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )

        if item_in.categoria_id is not None:
            from app.models.menu import CategoriaMenu
            from sqlalchemy import select
            statement = select(CategoriaMenu).where(
                CategoriaMenu.id == item_in.categoria_id
            )
            categoria = self.db.execute(statement).scalar_one_or_none()
            if not categoria:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontró la categoría con ID {item_in.categoria_id}"
                )

        if item_in.ingredientes_receta is not None:
            for receta in item_in.ingredientes_receta:
                insumo = self.insumo_repo.get_by_id(
                    receta.insumo_id
                )
                if not insumo:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"El insumo con ID {receta.insumo_id} "
                            f"no existe en el inventario"
                        )
                    )

        if item_in.nombre is not None and item_in.nombre.lower() != existing.nombre.lower():
            items_existentes = self.menu_repo.obtener_items()
            for item in items_existentes:
                if item.id != item_id and item.nombre.lower() == item_in.nombre.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ya existe otro plato con el nombre '{item_in.nombre}'"
                    )

        item_actualizado = self.menu_repo.actualizar_menu_item(item_id, item_in)
        return MenuItemResponse.model_validate(item_actualizado)

    def eliminar_platillo(self, item_id: int) -> None:
        existing = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )

        from app.models.menu import Receta
        from sqlalchemy import delete

        self.db.execute(
            delete(Receta).where(Receta.menu_item_id == item_id)
        )
        self.db.flush()

        self.menu_repo.eliminar_menu_item(item_id)
