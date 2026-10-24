from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.salon import Mesa, Zona


class OrdenRepository:
    """
    Repositorio para el módulo de Órdenes y Facturación.

    Maneja las operaciones de base de datos para órdenes
    de pedido y sus detalles (ítems del pedido).
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db

    def crear_orden(self, orden: Orden) -> Orden:
        """
        Agrega una nueva orden a la sesión de base de datos.

        La orden ya debe venir procesada con sus detalles
        y total calculado desde la capa de servicio.
        El commit se realiza externamente para controlar
        la transacción completa (inventario + mesa + orden).

        Args:
            orden: Instancia del modelo Orden con sus detalles.

        Returns:
            La orden agregada (pendiente de commit).
        """
        self.db.add(orden)
        return orden

    def obtener_por_id(self, orden_id: int) -> Optional[Orden]:
        """
        Obtiene una orden por su ID con sus detalles precargados.

        Utiliza joinedload para traer los detalles de forma
        eficiente en una sola consulta SQL.

        Args:
            orden_id: ID de la orden.

        Returns:
            La orden encontrada o None si no existe.
        """
        statement = (
            select(Orden)
            .options(
                joinedload(Orden.detalles),
                joinedload(Orden.mesa)
                    .joinedload(Mesa.zona),
                joinedload(Orden.mesero),
            )
            .where(Orden.id == orden_id)
        )
        result = self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    def obtener_ordenes_filtradas(
        self,
        estado: Optional[EstadoOrden] = None,
        mesa_id: Optional[int] = None
    ) -> List[Orden]:
        """
        Obtiene órdenes aplicando filtros dinámicos.

        Permite filtrar por:
        - Estado de la orden (ej: PREPARANDO para pantalla de cocina)
        - Mesa específica (ej: órdenes activas de una mesa)

        Usa joinedload para traer los detalles y ordena por
        fecha de creación descendente (más recientes primero).

        Args:
            estado: Estado para filtrar (opcional).
            mesa_id: ID de mesa para filtrar (opcional).

        Returns:
            Lista de órdenes que coinciden con los filtros.
        """
        statement = (
            select(Orden)
            .options(
                joinedload(Orden.detalles),
                joinedload(Orden.mesa)
                    .joinedload(Mesa.zona),
                joinedload(Orden.mesero),
            )
        )

        if estado is not None:
            statement = statement.where(Orden.estado == estado)

        if mesa_id is not None:
            statement = statement.where(Orden.mesa_id == mesa_id)

        statement = statement.order_by(Orden.fecha_creacion.desc())
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def actualizar_estado(
        self,
        orden: Orden,
        nuevo_estado: EstadoOrden
    ) -> Orden:
        """
        Actualiza el estado de una orden.

        Args:
            orden: Instancia de la orden a actualizar.
            nuevo_estado: Nuevo estado de la orden.

        Returns:
            La orden con el estado actualizado.
        """
        orden.estado = nuevo_estado
        self.db.commit()
        self.db.refresh(orden)
        return orden
