from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.descuento import DescuentoFrecuente
from app.repositories.descuento_repository import DescuentoFrecuenteRepository
from app.schemas.descuento import (
    DescuentoFrecuenteCreate,
    DescuentoFrecuenteUpdate,
    DescuentoFrecuenteResponse,
)


class DescuentoFrecuenteService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DescuentoFrecuenteRepository(db)

    def listar(self, solo_activos: bool = False) -> List[DescuentoFrecuenteResponse]:
        return [
            DescuentoFrecuenteResponse.model_validate(d)
            for d in self.repo.listar(solo_activos=solo_activos)
        ]

    def crear(self, data_in: DescuentoFrecuenteCreate) -> DescuentoFrecuenteResponse:
        nombre = data_in.nombre.strip()
        if self.repo.obtener_por_nombre(nombre):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un descuento con el nombre '{nombre}'",
            )
        data = DescuentoFrecuente(
            nombre=nombre,
            tipo=data_in.tipo,
            valor=data_in.valor,
            activo=True,
        )
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        return DescuentoFrecuenteResponse.model_validate(data)

    def actualizar(
        self,
        descuento_id: int,
        data_in: DescuentoFrecuenteUpdate,
    ) -> DescuentoFrecuenteResponse:
        data = self.repo.get_by_id(descuento_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el descuento con ID {descuento_id}",
            )
        if data_in.nombre is not None:
            nombre = data_in.nombre.strip()
            existente = self.repo.obtener_por_nombre(nombre)
            if existente and existente.id != descuento_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un descuento con el nombre '{nombre}'",
                )
            data.nombre = nombre
        if data_in.tipo is not None:
            data.tipo = data_in.tipo
        if data_in.valor is not None:
            data.valor = data_in.valor
        if data_in.activo is not None:
            data.activo = data_in.activo
        if data.tipo.value == "PORCENTAJE" and float(data.valor) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El porcentaje no puede ser mayor a 100",
            )
        self.db.commit()
        self.db.refresh(data)
        return DescuentoFrecuenteResponse.model_validate(data)

    def eliminar(self, descuento_id: int) -> None:
        data = self.repo.get_by_id(descuento_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el descuento con ID {descuento_id}",
            )
        self.db.delete(data)
        self.db.commit()
