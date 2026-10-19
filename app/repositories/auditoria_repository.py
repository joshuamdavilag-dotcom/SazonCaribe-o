from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria


class AuditoriaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def listar(
        self,
        desde: date | None,
        hasta: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RegistroAuditoria], int]:
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
