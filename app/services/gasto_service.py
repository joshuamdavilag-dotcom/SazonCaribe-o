from datetime import date, datetime
from decimal import Decimal
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.gasto import Gasto, CategoriaGasto
from app.repositories.gasto_repository import GastoRepository
from app.schemas.gasto import GastoCreate, GastoResponse


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
            gastos = self.repo.get_all(order_by="fecha")
        return [GastoResponse.model_validate(g) for g in gastos]

    def obtener_total_gastos(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Decimal:
        """Suma el monto total de gastos dentro de un rango de fechas."""
        return self.repo.sumar_por_rango(fecha_inicio, fecha_fin)
