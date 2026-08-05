from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.menu import CategoriaMenu, MenuItem, Receta
from app.schemas.menu import CategoriaMenuCreate, MenuItemCreate, MenuItemUpdate


class MenuRepository:
    """
    Repositorio para el módulo de Menú y Recetas.

    Maneja las operaciones de base de datos para categorías,
    platos del menú y recetas (ingredientes por plato).
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db

    # =========================================================================
    # Categorías
    # =========================================================================

    def crear_categoria(
        self,
        categoria_in: CategoriaMenuCreate
    ) -> CategoriaMenu:
        """
        Crea una nueva categoría del menú.

        Args:
            categoria_in: Datos de la categoría a crear.

        Returns:
            La categoría creada con su ID asignado.
        """
        categoria_data = categoria_in.model_dump()
        db_categoria = CategoriaMenu(**categoria_data)
        self.db.add(db_categoria)
        self.db.commit()
        self.db.refresh(db_categoria)
        return db_categoria

    def obtener_categorias(self) -> List[CategoriaMenu]:
        """
        Obtiene todas las categorías del menú.

        Returns:
            Lista de categorías ordenadas por nombre.
        """
        statement = (
            select(CategoriaMenu)
            .order_by(CategoriaMenu.nombre)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def obtener_categoria_por_id(self, categoria_id: int) -> Optional[CategoriaMenu]:
        """
        Obtiene una categoría por su ID.

        Args:
            categoria_id: ID de la categoría.

        Returns:
            La categoría encontrada o None si no existe.
        """
        statement = select(CategoriaMenu).where(
            CategoriaMenu.id == categoria_id
        )
        return self.db.execute(statement).scalar_one_or_none()

    def contar_items_por_categoria(self, categoria_id: int) -> int:
        statement = select(func.count(MenuItem.id)).where(
            MenuItem.categoria_id == categoria_id
        )
        return self.db.execute(statement).scalar_one()

    def eliminar_categoria(self, categoria_id: int) -> bool:
        db_categoria = self.obtener_categoria_por_id(categoria_id)
        if db_categoria is None:
            return False
        self.db.delete(db_categoria)
        self.db.commit()
        return True

    # =========================================================================
    # Platos del Menú (MenuItem)
    # =========================================================================

    def crear_menu_item(self, item_in: MenuItemCreate) -> MenuItem:
        item_data = item_in.model_dump(exclude={"receta"})
        db_item = MenuItem(**item_data)
        self.db.add(db_item)
        self.db.flush()

        if item_in.receta:
            for receta_in in item_in.receta:
                db_receta = Receta(
                    menu_item_id=db_item.id,
                    insumo_id=receta_in.insumo_id,
                    cantidad_necesaria=receta_in.cantidad_necesaria,
                    descuento_por_lote=receta_in.descuento_por_lote
                )
                self.db.add(db_receta)

        self.db.commit()
        self.db.refresh(db_item)
        return db_item

    def eliminar_menu_item(self, item_id: int) -> bool:
        """
        Borrado lógico (soft delete) de un plato.

        En lugar de eliminar físicamente el registro (lo que rompería el
        historial de ventas referenciado en ``detalle_orden``), marca el
        plato como ``disponible = False`` para ocultarlo de comandas y de
        la carta pública, conservando su receta y su historial.

        Args:
            item_id: ID del plato a desactivar.

        Returns:
            True si el plato existía y se desactivó; False si no existe.
        """
        statement = select(MenuItem).where(MenuItem.id == item_id)
        db_item = self.db.execute(statement).scalar_one_or_none()
        if db_item is None:
            return False
        db_item.disponible = False
        self.db.commit()
        return True

    def _query_items_base(self, incluir_insumos: bool = True):
        """
        Construye la consulta base de MenuItem con sus relaciones cargadas.

        Método reutilizable por las consultas administrativas y públicas.
        Cuando ``incluir_insumos`` es False, NO se cargan recetas ni insumos
        (información interna del inventario) para evitar exponer costos.

        Args:
            incluir_insumos: Si True, carga recetas e insumos (uso interno).

        Returns:
            Sentencia select de MenuItem con las relaciones configuradas.
        """
        opciones = [joinedload(MenuItem.categoria)]
        if incluir_insumos:
            opciones.append(
                joinedload(MenuItem.ingredientes_receta)
                    .joinedload(Receta.insumo)
            )
        return select(MenuItem).options(*opciones)

    def obtener_items(
        self,
        categoria_id: Optional[int] = None,
        incluir_inactivos: bool = False
    ) -> List[MenuItem]:
        """
        Obtiene los platos del menú con sus relaciones (uso administrativo).

        Por defecto solo devuelve platos activos (``disponible = True``),
        que es lo que necesitan comandas y carta. La pestaña de Gestión de
        Menú pasa ``incluir_inactivos = True`` para ver también los platos
        desactivados por borrado lógico.

        Usa joinedload para traer de forma eficiente:
        - La categoría asociada
        - Las recetas (ingredientes del plato)
        - Los ingredientes de cada receta

        Args:
            categoria_id: Si se proporciona, filtra por esta categoría.
            incluir_inactivos: Si True, incluye los platos desactivados.

        Returns:
            Lista de platos con sus relaciones cargadas.
        """
        statement = self._query_items_base(incluir_insumos=True)

        if not incluir_inactivos:
            statement = statement.where(
                MenuItem.disponible.is_(True)
            )

        if categoria_id is not None:
            statement = statement.where(
                MenuItem.categoria_id == categoria_id
            )

        statement = statement.order_by(MenuItem.nombre)
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def obtener_menu_item_por_id(self, item_id: int) -> Optional[MenuItem]:
        """
        Obtiene un plato por su ID con sus relaciones cargadas
        (uso administrativo).

        Args:
            item_id: ID del plato.

        Returns:
            El plato encontrado o None si no existe.
        """
        statement = (
            self._query_items_base(incluir_insumos=True)
            .where(MenuItem.id == item_id)
        )
        result = self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    # =========================================================================
    # Consultas públicas (futura Carta Digital) — solo lectura
    # =========================================================================

    def obtener_items_publicos(
        self,
        categoria_id: Optional[int] = None
    ) -> List[MenuItem]:
        """
        Obtiene únicamente los platos disponibles para la carta pública.

        Reutilizable por la futura Carta Digital. NO carga recetas ni insumos
        (información interna del inventario). Solo devuelve platos con
        ``disponible = True``.

        Args:
            categoria_id: Si se proporciona, filtra por esta categoría.

        Returns:
            Lista de platos disponibles con su categoría cargada.
        """
        statement = self._query_items_base(incluir_insumos=False).where(
            MenuItem.disponible.is_(True)
        )

        if categoria_id is not None:
            statement = statement.where(
                MenuItem.categoria_id == categoria_id
            )

        statement = statement.order_by(MenuItem.nombre)
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def obtener_item_publico_por_id(self, item_id: int) -> Optional[MenuItem]:
        """
        Obtiene un plato disponible por su ID para la carta pública.

        Reutilizable por la futura Carta Digital. NO carga recetas ni insumos
        (información interna del inventario). Solo devuelve el plato si está
        disponible.

        Args:
            item_id: ID del plato.

        Returns:
            El plato disponible encontrado o None si no existe o no está disponible.
        """
        statement = (
            self._query_items_base(incluir_insumos=False)
            .where(
                MenuItem.id == item_id,
                MenuItem.disponible.is_(True)
            )
        )
        result = self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    def actualizar_menu_item(
        self,
        item_id: int,
        item_in: MenuItemUpdate
    ) -> Optional[MenuItem]:
        """
        Actualiza un plato del menú con datos parciales.

        Flujo:
        1. Busca el plato por ID.
        2. Actualiza solo los campos proporcionados (no nulos).
        3. Si se proporciona una nueva receta, elimina la anterior y crea la nueva.
        4. Commit y refresh.

        Args:
            item_id: ID del plato a actualizar.
            item_in: Datos parciales a actualizar.

        Returns:
            El plato actualizado o None si no existe.
        """
        item = self.obtener_menu_item_por_id(item_id)
        if item is None:
            return None

        update_data = item_in.model_dump(exclude_unset=True)
        receta_nueva = update_data.pop("ingredientes_receta", None)

        for field, value in update_data.items():
            setattr(item, field, value)

        if receta_nueva is not None:
            for receta_existente in list(item.ingredientes_receta):
                self.db.delete(receta_existente)
            self.db.flush()

            for receta_in in receta_nueva:
                db_receta = Receta(
                    menu_item_id=item.id,
                    insumo_id=receta_in.insumo_id,
                    cantidad_necesaria=receta_in.cantidad_necesaria,
                    descuento_por_lote=receta_in.descuento_por_lote
                )
                self.db.add(db_receta)

        self.db.commit()
        self.db.refresh(item)
        return item

    def actualizar_imagen_url(
        self,
        item_id: int,
        imagen_url: Optional[str]
    ) -> Optional[MenuItem]:
        """
        Asigna la ruta de imagen de un plato.

        Solo el servidor invoca este método (al procesar un archivo subido);
        los clientes nunca envían rutas manualmente.

        Args:
            item_id: ID del plato a actualizar.
            imagen_url: Ruta del archivo de imagen, o None para limpiarla.

        Returns:
            El plato actualizado o None si no existe.
        """
        item = self.obtener_menu_item_por_id(item_id)
        if item is None:
            return None
        item.imagen_url = imagen_url
        self.db.commit()
        self.db.refresh(item)
        return item
