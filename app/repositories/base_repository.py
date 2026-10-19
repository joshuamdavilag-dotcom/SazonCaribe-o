from typing import TypeVar, Generic, Optional, List, Type

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Repositorio genérico con operaciones CRUD estándar.

    Proporciona métodos básicos para cualquier modelo SQLAlchemy.
    """

    def __init__(self, model: Type[ModelType], db: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            model: Clase del modelo SQLAlchemy.
            db: Sesión de base de datos.
        """
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Obtiene un registro por su ID.

        Args:
            id: Identificador del registro.

        Returns:
            El registro encontrado o None si no existe.
        """
        statement = select(self.model).where(self.model.id == id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """
        Obtiene todos los registros con paginación.

        Args:
            skip: Registros a omitir.
            limit: Número máximo de registros a retornar.
            order_by: Campo para ordenar (opcional).

        Returns:
            Lista de registros encontrados.
        """
        statement = select(self.model)

        if order_by and hasattr(self.model, order_by):
            statement = statement.order_by(getattr(self.model, order_by))

        statement = statement.offset(skip).limit(limit)
        result = self.db.execute(statement)
        return list(result.scalars().all())

    def count(self) -> int:
        """
        Cuenta el total de registros.

        Returns:
            Número total de registros.
        """
        statement = select(func.count()).select_from(self.model)
        return self.db.execute(statement).scalar_one()

    def create(self, obj_data: dict) -> ModelType:
        """
        Crea un nuevo registro.

        Args:
            obj_data: Diccionario con los datos del registro.

        Returns:
            El registro creado con su ID asignado.
        """
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, id: int, obj_data: dict) -> Optional[ModelType]:
        """
        Actualiza un registro existente.

        Args:
            id: Identificador del registro a actualizar.
            obj_data: Diccionario con los campos a actualizar.

        Returns:
            El registro actualizado o None si no existe.
        """
        db_obj = self.get_by_id(id)
        if db_obj is None:
            return None

        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> bool:
        """
        Elimina un registro por su ID.

        Args:
            id: Identificador del registro a eliminar.

        Returns:
            True si se eliminó, False si no se encontró.
        """
        db_obj = self.get_by_id(id)
        if db_obj is None:
            return False

        self.db.delete(db_obj)
        self.db.commit()
        return True
