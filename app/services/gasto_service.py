from datetime import date, datetime
from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local
from app.models.gasto import Gasto, CategoriaGasto
from app.models.personal import Usuario
from app.repositories.gasto_repository import GastoRepository
from app.schemas.gasto import GastoCreate, GastoUpdate, GastoResponse
from app.services.auditoria_service import AuditoriaService


class GastoService:
    """Gestiona los gastos operativos y los auto-generados por inventario."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = GastoRepository(db)

    def registrar_gasto(
        self,
        gasto_in: GastoCreate,
        usuario_id: int | None = None,
    ) -> GastoResponse:
        """Registra un gasto manual y lo persiste en la base de datos.

        Args:
            gasto_in: Datos del gasto a registrar.
            usuario_id: ID del usuario que registra el gasto (opcional).

        Returns:
            GastoResponse con el gasto creado.
        """
        kwargs = {}
        if gasto_in.fecha:
            kwargs["fecha"] = datetime.combine(gasto_in.fecha, datetime.now().time())
        data = Gasto(
            concepto=gasto_in.concepto,
            monto=gasto_in.monto,
            categoria=gasto_in.categoria,
            registrado_por=usuario_id,
            insumo_id=gasto_in.insumo_id,
            **kwargs,
        )
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        return GastoResponse.model_validate(data)

    def registrar_gasto_automatico(
        self,
        insumo_id: int,
        concepto: str,
        monto: Decimal,
    ) -> Gasto:
        """Crea un gasto de SUMINISTROS sin commit, usado por movimientos de inventario.

        Args:
            insumo_id: ID del insumo que origina el gasto.
            concepto: Descripción del gasto.
            monto: Monto del gasto (cantidad × costo unitario).

        Returns:
            El gasto agregado a la sesión (requiere flush/commit del caller).
        """
        gasto = Gasto(
            concepto=concepto,
            monto=monto,
            categoria=CategoriaGasto.SUMINISTROS,
            insumo_id=insumo_id,
        )
        self.db.add(gasto)
        self.db.flush()
        return gasto

    def listar_gastos(
        self,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
    ) -> List[GastoResponse]:
        """Lista los gastos, filtrando por rango de fechas cuando se indica.

        Args:
            fecha_inicio: Fecha inicial del filtro (opcional).
            fecha_fin: Fecha final del filtro (opcional).

        Returns:
            Lista de GastoResponse.
        """
        if fecha_inicio and fecha_fin:
            gastos = self.repo.obtener_por_rango(fecha_inicio, fecha_fin)
        else:
            gastos = self.repo.listar_todos()
        return [GastoResponse.model_validate(g) for g in gastos]

    def obtener_total_gastos(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """Suma el monto total de gastos dentro de un rango de fechas."""
        return self.repo.sumar_por_rango(fecha_inicio, fecha_fin)

    def editar_gasto(
        self,
        gasto_id: int,
        gasto_in: "GastoUpdate",
        actor: Usuario,
    ) -> GastoResponse:
        """Edita un gasto existente dejando rastro de antes/después en auditoría.

        Args:
            gasto_id: ID del gasto a editar.
            gasto_in: Campos a modificar (todos opcionales) + motivo obligatorio.
            actor: Usuario que realiza la modificación.

        Raises:
            HTTPException 404: si el gasto no existe.
            HTTPException 400: si el gasto está eliminado o no hay cambios.
            HTTPException 400: si el motivo está vacío.
        """
        motivo = (gasto_in.motivo or "").strip()
        if not motivo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El motivo de la modificación es obligatorio.",
            )

        gasto = self.repo.obtener_por_id(gasto_id)
        if not gasto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el gasto con ID {gasto_id}",
            )
        if gasto.eliminado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar un gasto eliminado.",
            )

        antes = {
            "concepto": gasto.concepto,
            "monto": str(Decimal(str(gasto.monto)).quantize(Decimal("0.01"))),
            "categoria": gasto.categoria.value if gasto.categoria else None,
            "fecha": gasto.fecha.isoformat() if gasto.fecha else None,
        }

        if gasto_in.concepto is not None:
            gasto.concepto = gasto_in.concepto
        if gasto_in.monto is not None:
            gasto.monto = gasto_in.monto
        if gasto_in.categoria is not None:
            gasto.categoria = gasto_in.categoria
        if gasto_in.fecha is not None:
            hora = gasto.fecha.time() if gasto.fecha else datetime.now().time()
            gasto.fecha = datetime.combine(gasto_in.fecha, hora)

        despues = {
            "concepto": gasto.concepto,
            "monto": str(Decimal(str(gasto.monto)).quantize(Decimal("0.01"))),
            "categoria": gasto.categoria.value if gasto.categoria else None,
            "fecha": gasto.fecha.isoformat() if gasto.fecha else None,
        }
        antes["fecha"] = (antes["fecha"] or "")[:19]
        despues["fecha"] = (despues["fecha"] or "")[:19]
        if antes == despues:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay cambios que guardar.",
            )

        try:
            with self.db.begin_nested():
                AuditoriaService.registrar(
                    self.db,
                    actor,
                    "GASTO_EDITADO",
                    "gasto",
                    gasto.id,
                    f"Gasto #{gasto.id} modificado — motivo: {motivo}",
                    antes=antes,
                    despues={**despues, "motivo": motivo},
                )
            self.db.commit()
            self.db.refresh(gasto)
            return GastoResponse.model_validate(gasto)

        except Exception:
            self.db.rollback()
            raise

    def eliminar_gasto(
        self,
        gasto_id: int,
        motivo: str,
        actor: Usuario,
    ) -> GastoResponse:
        """Elimina (borrado lógico) un gasto dejando el motivo en auditoría.

        El gasto desaparece de listados y totales, pero permanece consultable
        en la bitácora. No toca inventario aunque sea un SUMINISTROS automático.

        Raises:
            HTTPException 404: si el gasto no existe.
            HTTPException 400: si ya está eliminado o el motivo está vacío.
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El motivo de la eliminación es obligatorio.",
            )

        gasto = self.repo.obtener_por_id(gasto_id)
        if not gasto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el gasto con ID {gasto_id}",
            )
        if gasto.eliminado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El gasto ya está eliminado.",
            )

        antes = {
            "concepto": gasto.concepto,
            "monto": str(gasto.monto),
            "categoria": gasto.categoria.value if gasto.categoria else None,
            "fecha": gasto.fecha.isoformat() if gasto.fecha else None,
            "insumo_id": gasto.insumo_id,
            "cierre_caja_id": gasto.cierre_caja_id,
        }

        try:
            with self.db.begin_nested():
                gasto.eliminado = True
                gasto.motivo_eliminacion = motivo
                gasto.eliminado_por = actor.id
                gasto.eliminado_en = ahora_local()

                AuditoriaService.registrar(
                    self.db,
                    actor,
                    "GASTO_ELIMINADO",
                    "gasto",
                    gasto.id,
                    f"Gasto #{gasto.id} ({gasto.concepto} · C${gasto.monto}) eliminado — motivo: {motivo}",
                    antes=antes,
                    despues={"eliminado": True, "motivo": motivo},
                )

            self.db.commit()
            self.db.refresh(gasto)
            return GastoResponse.model_validate(gasto)

        except Exception:
            self.db.rollback()
            raise
