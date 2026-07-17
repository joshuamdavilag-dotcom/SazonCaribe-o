from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventario import (
    Proveedor, Ingrediente, Insumo, MovimientoInventario,
    CategoriaInsumo, UnidadMedida,
)
from app.repositories.base_repository import BaseRepository


class ProveedorRepository(BaseRepository[Proveedor]):
    """
    Repositorio para el modelo Proveedor.

    Extiende BaseRepository con métodos específicos
    para la gestión de proveedores del restaurante.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Proveedor, db)


class IngredienteRepository(BaseRepository[Ingrediente]):
    """
    Repositorio para el modelo Ingrediente.

    Extiende BaseRepository con métodos específicos
    para la gestión de ingredientes y control de stock.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Ingrediente, db)

    def get_bajo_stock_minimo(self) -> List[Ingrediente]:
        """
        Obtiene todos los ingredientes por debajo del stock mínimo.

        Útil para alertas de reabastecimiento y generación
        automática de órdenes de compra.

        Returns:
            Lista de ingredientes donde stock_actual <= stock_minimo.
        """
        statement = (
            select(Ingrediente)
            .where(Ingrediente.stock_actual <= Ingrediente.stock_minimo)
            .order_by(Ingrediente.stock_actual)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_by_nombre(self, nombre: str) -> List[Ingrediente]:
        """
        Busca ingredientes por nombre (búsqueda parcial).

        Args:
            nombre: Término de búsqueda.

        Returns:
            Lista de ingredientes que coinciden con el término.
        """
        statement = (
            select(Ingrediente)
            .where(Ingrediente.nombre.ilike(f"%{nombre}%"))
            .order_by(Ingrediente.nombre)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def actualizar_stock(
        self,
        ingrediente_id: int,
        cantidad: Decimal,
        tipo_movimiento: str
    ) -> Ingrediente:
        """
        Actualiza el stock de un ingrediente según el tipo de movimiento.

        Para 'ENTRADA' suma la cantidad, para 'SALIDA' la resta.

        Args:
            ingrediente_id: ID del ingrediente.
            cantidad: Cantidad a agregar o restar.
            tipo_movimiento: 'ENTRADA' o 'SALIDA'.

        Returns:
            El ingrediente con el stock actualizado.

        Raises:
            ValueError: Si el tipo de movimiento no es válido.
            ValueError: Si no hay stock suficiente para una salida.
        """
        ingrediente = self.get_by_id(ingrediente_id)
        if ingrediente is None:
            raise ValueError(
                f"No se encontró el ingrediente con ID {ingrediente_id}"
            )

        if tipo_movimiento == "ENTRADA":
            ingrediente.stock_actual += cantidad
        elif tipo_movimiento == "SALIDA":
            if ingrediente.stock_actual < cantidad:
                raise ValueError(
                    f"Stock insuficiente. Disponible: {ingrediente.stock_actual}, "
                    f"Solicitado: {cantidad}"
                )
            ingrediente.stock_actual -= cantidad
        else:
            raise ValueError(
                f"Tipo de movimiento no válido: {tipo_movimiento}. "
                "Debe ser 'ENTRADA' o 'SALIDA'."
            )

        self.db.commit()
        self.db.refresh(ingrediente)
        return ingrediente


class MovimientoInventarioRepository(BaseRepository[MovimientoInventario]):
    """
    Repositorio para el modelo MovimientoInventario.

    Extiende BaseRepository con métodos específicos
    para el seguimiento de movimientos de inventario.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(MovimientoInventario, db)

    def get_by_insumo(self, insumo_id: int) -> List[MovimientoInventario]:
        """
        Obtiene el historial de movimientos de un insumo específico.

        Args:
            insumo_id: ID del insumo.

        Returns:
            Lista de movimientos ordenados por fecha descendente (más reciente primero).
        """
        statement = (
            select(MovimientoInventario)
            .where(MovimientoInventario.insumo_id == insumo_id)
            .order_by(MovimientoInventario.fecha.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_by_tipo(self, tipo: str) -> List[MovimientoInventario]:
        """
        Obtiene todos los movimientos de un tipo específico (ENTRADA o SALIDA).

        Args:
            tipo: Tipo de movimiento ('ENTRADA' o 'SALIDA').

        Returns:
            Lista de movimientos del tipo especificado.
        """
        statement = (
            select(MovimientoInventario)
            .where(MovimientoInventario.tipo == tipo)
            .order_by(MovimientoInventario.fecha.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_by_insumo_y_tipo(
        self,
        insumo_id: int,
        tipo: str
    ) -> List[MovimientoInventario]:
        """
        Obtiene movimientos de un insumo filtrados por tipo.

        Args:
            insumo_id: ID del insumo.
            tipo: Tipo de movimiento ('ENTRADA' o 'SALIDA').

        Returns:
            Lista de movimientos que coinciden con los criterios.
        """
        statement = (
            select(MovimientoInventario)
            .where(
                MovimientoInventario.insumo_id == insumo_id,
                MovimientoInventario.tipo == tipo
            )
            .order_by(MovimientoInventario.fecha.desc())
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())


class InsumoRepository(BaseRepository[Insumo]):
    """
    Repositorio para el modelo Insumo.

    Extiende BaseRepository con métodos específicos
    para la gestión de insumos generales del restaurante.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Insumo, db)

    def get_by_nombre(self, nombre: str) -> List[Insumo]:
        """
        Busca insumos por nombre (búsqueda parcial).

        Args:
            nombre: Término de búsqueda.

        Returns:
            Lista de insumos que coinciden con el término.
        """
        statement = (
            select(Insumo)
            .where(Insumo.nombre.ilike(f"%{nombre}%"))
            .order_by(Insumo.nombre)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def get_bajo_stock_minimo(self) -> List[Insumo]:
        """
        Obtiene todos los insumos por debajo del stock mínimo.

        Returns:
            Lista de insumos donde cantidad_actual <= stock_minimo.
        """
        statement = (
            select(Insumo)
            .where(Insumo.cantidad_actual <= Insumo.stock_minimo)
            .order_by(Insumo.cantidad_actual)
        )
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def actualizar_stock(
        self,
        insumo_id: int,
        cantidad: Decimal,
        tipo_movimiento: str
    ) -> Insumo:
        """
        Actualiza el stock de un insumo según el tipo de movimiento.

        Para 'ENTRADA' suma la cantidad, para 'SALIDA' la resta.

        Args:
            insumo_id: ID del insumo.
            cantidad: Cantidad a agregar o restar.
            tipo_movimiento: 'ENTRADA' o 'SALIDA'.

        Returns:
            El insumo con el stock actualizado.

        Raises:
            ValueError: Si el insumo no existe.
            ValueError: Si el tipo de movimiento no es válido.
            ValueError: Si no hay stock suficiente para una salida.
        """
        insumo = self.get_by_id(insumo_id)
        if insumo is None:
            raise ValueError(
                f"No se encontró el insumo con ID {insumo_id}"
            )

        if tipo_movimiento == "ENTRADA":
            insumo.cantidad_actual += cantidad
        elif tipo_movimiento == "SALIDA":
            if insumo.cantidad_actual < cantidad:
                raise ValueError(
                    f"Stock insuficiente. Disponible: {insumo.cantidad_actual}, "
                    f"Solicitado: {cantidad}"
                )
            insumo.cantidad_actual -= cantidad
        else:
            raise ValueError(
                f"Tipo de movimiento no válido: {tipo_movimiento}. "
                "Debe ser 'ENTRADA' o 'SALIDA'."
            )

        self.db.commit()
        self.db.refresh(insumo)
        return insumo


class CategoriaInsumoRepository(BaseRepository[CategoriaInsumo]):
    def __init__(self, db: Session) -> None:
        super().__init__(CategoriaInsumo, db)

    def contar_insumos_por_categoria(self, categoria_id: int) -> int:
        statement = select(Insumo).where(Insumo.categoria_id == categoria_id)
        return len(list(self.db.execute(statement).scalars().all()))


class UnidadMedidaRepository(BaseRepository[UnidadMedida]):
    def __init__(self, db: Session) -> None:
        super().__init__(UnidadMedida, db)

    def contar_insumos_por_unidad(self, unidad_id: int) -> int:
        statement = select(Insumo).where(Insumo.unidad_medida_id == unidad_id)
        return len(list(self.db.execute(statement).scalars().all()))
