from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.salon import Zona, Mesa, EstadoMesa
from app.schemas.salon import ZonaCreate, MesaCreate


class SalonRepository:
    """
    Repositorio para el módulo de Salón y Mesas.

    Maneja las operaciones de base de datos para zonas,
    mesas y la gestión de estados del restaurante.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db

    # =========================================================================
    # Zonas
    # =========================================================================

    def crear_zona(self, zona_in: ZonaCreate) -> Zona:
        """
        Crea una nueva zona en el restaurante.

        Args:
            zona_in: Datos de la zona a crear.

        Returns:
            La zona creada con su ID asignado.
        """
        zona_data = zona_in.model_dump()
        db_zona = Zona(**zona_data)
        self.db.add(db_zona)
        self.db.commit()
        self.db.refresh(db_zona)
        return db_zona

    def obtener_zonas_con_mesas(self) -> List[Zona]:
        """
        Obtiene todas las zonas con sus mesas precargadas.

        Utiliza joinedload para traer las mesas de forma eficiente
        en una sola consulta SQL optimizada.

        Returns:
            Lista de zonas con sus mesas asociadas.
        """
        statement = (
            select(Zona)
            .options(joinedload(Zona.mesas))
            .order_by(Zona.nombre)
        )
        result = self.db.execute(statement)
        return list(result.unique().scalars().all())

    def obtener_zona_por_id(self, zona_id: int) -> Optional[Zona]:
        """
        Obtiene una zona por su ID.

        Args:
            zona_id: ID de la zona.

        Returns:
            La zona encontrada o None si no existe.
        """
        statement = select(Zona).where(Zona.id == zona_id)
        return self.db.execute(statement).scalar_one_or_none()

    def contar_mesas_por_zona(self, zona_id: int) -> int:
        statement = select(func.count(Mesa.id)).where(Mesa.zona_id == zona_id)
        return self.db.execute(statement).scalar_one()

    def eliminar_zona(self, zona_id: int) -> bool:
        db_zona = self.obtener_zona_por_id(zona_id)
        if db_zona is None:
            return False
        self.db.delete(db_zona)
        self.db.commit()
        return True

    # =========================================================================
    # Mesas
    # =========================================================================

    def crear_mesa(self, mesa_in: MesaCreate) -> Mesa:
        """
        Crea una nueva mesa en el restaurante.

        Args:
            mesa_in: Datos de la mesa a crear.

        Returns:
            La mesa creada con su ID asignado.
        """
        mesa_data = mesa_in.model_dump()
        db_mesa = Mesa(**mesa_data)
        self.db.add(db_mesa)
        self.db.commit()
        self.db.refresh(db_mesa)
        return db_mesa

    def obtener_mesa_por_id(self, mesa_id: int) -> Optional[Mesa]:
        """
        Obtiene una mesa por su ID.

        Args:
            mesa_id: ID de la mesa.

        Returns:
            La mesa encontrada o None si no existe.
        """
        statement = select(Mesa).where(Mesa.id == mesa_id)
        return self.db.execute(statement).scalar_one_or_none()

    def obtener_mesas_filtradas(
        self,
        estados: Optional[List[EstadoMesa]] = None
    ) -> List[Mesa]:
        """
        Obtiene mesas filtradas por estado.

        Si se proporciona una lista de estados, filtra las mesas
        que estén en alguno de esos estados. Si no se proporciona,
        retorna todas las mesas.

        Args:
            estados: Lista de estados para filtrar (opcional).

        Returns:
            Lista de mesas que coinciden con el filtro.
        """
        statement = select(Mesa)

        if estados:
            statement = statement.where(Mesa.estado.in_(estados))

        statement = statement.order_by(Mesa.zona_id, Mesa.numero)
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def actualizar_estado_mesa(
        self,
        mesa_id: int,
        nuevo_estado: EstadoMesa
    ) -> Optional[Mesa]:
        db_mesa = self.obtener_mesa_por_id(mesa_id)
        if db_mesa is None:
            return None
        db_mesa.estado = nuevo_estado
        self.db.commit()
        self.db.refresh(db_mesa)
        return db_mesa

    def actualizar_mesa(self, mesa_id: int, **kwargs) -> Optional[Mesa]:
        db_mesa = self.obtener_mesa_por_id(mesa_id)
        if db_mesa is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(db_mesa, key):
                setattr(db_mesa, key, value)
        self.db.commit()
        self.db.refresh(db_mesa)
        return db_mesa

    def eliminar_mesa(self, mesa_id: int) -> bool:
        db_mesa = self.obtener_mesa_por_id(mesa_id)
        if db_mesa is None:
            return False
        self.db.delete(db_mesa)
        self.db.commit()
        return True
