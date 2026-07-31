from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.caja_repository import CajaRepository
from app.repositories.orden_repository import OrdenRepository
from app.schemas.caja import CierreCajaResponse, HistorialDiarioResponse
from app.schemas.orden import OrdenResponse


class CajaService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.caja_repo = CajaRepository(db)
        self.orden_repo = OrdenRepository(db)

    def historial_diario(self) -> HistorialDiarioResponse:
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()
        totales = self.caja_repo.calcular_totales(ordenes)

        return HistorialDiarioResponse(
            fecha=date.today().isoformat(),
            total_ventas=totales["total_ventas"],
            total_ordenes=totales["total_ordenes"],
            ordenes=[
                OrdenResponse.model_validate(o) for o in ordenes
            ],
        )

    def cerrar_caja(
        self,
        usuario_id: int,
    ) -> CierreCajaResponse:
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()

        if not ordenes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay órdenes pagadas sin archivar.",
            )

        totales = self.caja_repo.calcular_totales(ordenes)
        gastos = self.caja_repo.obtener_gastos_sin_archivar()

        try:
            with self.db.begin_nested():
                cierre = self.caja_repo.crear_cierre(
                    total_ventas=totales["total_ventas"],
                    total_ordenes=totales["total_ordenes"],
                    cerrado_por=usuario_id,
                )
                if cierre.id is None:
                    raise ValueError("El cierre de caja no obtuvo un id tras el flush.")
                self.caja_repo.archivar_ordenes(ordenes, cierre)
                self.caja_repo.archivar_gastos(gastos, cierre)

            self.db.commit()
            self.db.refresh(cierre)
            return CierreCajaResponse.model_validate(cierre)

        except Exception as exc:
            self.db.rollback()
            print(f"[X] Error en cerrar_caja: {exc}")
            raise
