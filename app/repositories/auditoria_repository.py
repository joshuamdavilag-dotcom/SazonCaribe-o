from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria


class AuditoriaRepository:
    """Acceso a datos de la bitácora de auditoría."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar(
        self,
        desde: date | None,
        hasta: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RegistroAuditoria], int]:
        """Devuelve una página de registros (más recientes primero) y el total sin paginar.

        Args:
            desde: Fecha inicial inclusiva; None para no filtrar por inicio.
            hasta: Fecha final inclusiva; None para no filtrar por fin.
            limit: Máximo de registros a devolver.
            offset: Registros a omitir (paginación).

        Returns:
            Tupla ``(registros, total)`` donde ``total`` es el conteo completo del filtro.
        """
        statement = select(RegistroAuditoria)
        count_statement = select(func.count()).select_from(RegistroAuditoria)

        if desde is not None:
            inicio = datetime.combine(desde, time.min)
            statement = statement.where(RegistroAuditoria.ocurrido_en >= inicio)
            count_statement = count_statement.where(
                RegistroAuditoria.ocurrido_en >= inicio
            )
        if hasta is not None:
            fin_exclusivo = datetime.combine(hasta + timedelta(days=1), time.min)
            statement = statement.where(RegistroAuditoria.ocurrido_en < fin_exclusivo)
            count_statement = count_statement.where(
                RegistroAuditoria.ocurrido_en < fin_exclusivo
            )

        total = self.db.execute(count_statement).scalar_one()
        rows = self.db.execute(
            statement
            .order_by(RegistroAuditoria.ocurrido_en.desc(), RegistroAuditoria.id.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
        return list(rows), total
