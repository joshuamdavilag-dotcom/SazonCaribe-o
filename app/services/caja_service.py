from datetime import date, datetime
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.caja import CierreCaja
from app.models.orden import Orden
from app.repositories.caja_repository import CajaRepository
from app.repositories.orden_repository import OrdenRepository
from app.schemas.caja import CierreCajaResponse, HistorialDiarioResponse
from app.schemas.orden import OrdenResponse


class CajaService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.caja_repo = CajaRepository(db)
        self.orden_repo = OrdenRepository(db)

    def historial_diario(
        self,
        fecha_consulta: date,
    ) -> HistorialDiarioResponse:
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar(
            fecha_consulta
        )
        totales = self.caja_repo.calcular_totales(ordenes)

        return HistorialDiarioResponse(
            fecha=fecha_consulta.isoformat(),
            total_ventas=totales["total_ventas"],
            total_ordenes=totales["total_ordenes"],
            ordenes=[
                OrdenResponse.model_validate(o) for o in ordenes
            ],
        )

    def cerrar_caja(
        self,
        fecha_consulta: date,
        usuario_id: int,
    ) -> CierreCajaResponse:
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar(
            fecha_consulta
        )

        if not ordenes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay órdenes pagadas para archivar en la fecha indicada.",
            )

        totales = self.caja_repo.calcular_totales(ordenes)

        try:
            with self.db.begin_nested():
                cierre = self.caja_repo.crear_cierre(
                    total_ventas=totales["total_ventas"],
                    total_ordenes=totales["total_ordenes"],
                    cerrado_por=usuario_id,
                )
                self.caja_repo.archivar_ordenes(ordenes, cierre)

            self.db.commit()
            self.db.refresh(cierre)
            return CierreCajaResponse.model_validate(cierre)

        except Exception:
            self.db.rollback()
            raise
