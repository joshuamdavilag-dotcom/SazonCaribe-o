from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventario import PreparacionCocina, DetallePreparacionCocina, MovimientoInventario
from app.repositories.inventario_repository import (
    InsumoRepository,
    MovimientoInventarioRepository,
    PreparacionCocinaRepository,
)
from app.schemas.inventario import (
    PreparacionCocinaCreate,
    PreparacionCocinaResponse,
)
from app.services.gasto_service import GastoService


class PreparacionService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.insumo_repo = InsumoRepository(db)
        self.movimiento_repo = MovimientoInventarioRepository(db)
        self.preparacion_repo = PreparacionCocinaRepository(db)
        self.gasto_service = GastoService(db)

    def registrar_preparacion(
        self,
        data: PreparacionCocinaCreate,
        usuario_id: int,
        asistencia_id: int | None = None,
    ) -> PreparacionCocinaResponse:
        for det in data.detalles:
            insumo = self.insumo_repo.get_by_id(det.insumo_id)
            if not insumo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontró el insumo con ID {det.insumo_id}",
                )
            if Decimal(str(insumo.cantidad_actual)) < det.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Stock insuficiente para '{insumo.nombre}': "
                        f"disponible {insumo.cantidad_actual}, "
                        f"requerido {det.cantidad}"
                    ),
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        preparacion = PreparacionCocina(
            asistencia_id=asistencia_id,
            notas=data.notas,
            fecha=now,
            registrado_por=usuario_id,
        )
        self.db.add(preparacion)
        self.db.flush()

        for det in data.detalles:
            insumo = self.insumo_repo.get_by_id(det.insumo_id)
            costo_unitario = Decimal(str(insumo.costo_unitario))
            costo_total = det.cantidad * costo_unitario

            insumo.cantidad_actual -= det.cantidad
            self.db.add(MovimientoInventario(
                insumo_id=insumo.id,
                tipo="SALIDA",
                cantidad=det.cantidad,
                motivo=f"Producción de Cocina — Preparación #{preparacion.id}",
                fecha=now,
            ))
            if costo_total > 0:
                self.gasto_service.registrar_gasto_automatico(
                    insumo_id=insumo.id,
                    concepto=f"Producción de Cocina: {insumo.nombre} — Prep #{preparacion.id}",
                    monto=costo_total,
                )

            detalle = DetallePreparacionCocina(
                preparacion_id=preparacion.id,
                insumo_id=insumo.id,
                cantidad=det.cantidad,
                costo_total=costo_total,
            )
            self.db.add(detalle)

        self.db.commit()
        self.db.refresh(preparacion)
        return PreparacionCocinaResponse.model_validate(preparacion)

    def listar_por_fecha(self, fecha) -> List[PreparacionCocinaResponse]:
        preparaciones = self.preparacion_repo.get_por_rango_fechas(fecha, fecha)
        return [PreparacionCocinaResponse.model_validate(p) for p in preparaciones]

    def listar_por_asistencia(self, asistencia_id: int) -> List[PreparacionCocinaResponse]:
        preparaciones = self.preparacion_repo.get_por_asistencia(asistencia_id)
        return [PreparacionCocinaResponse.model_validate(p) for p in preparaciones]
