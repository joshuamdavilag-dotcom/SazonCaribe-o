from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria
from app.models.personal import Usuario
from app.repositories.auditoria_repository import AuditoriaRepository
from app.schemas.auditoria import (
    AuditoriaPageResponse,
    RegistroAuditoriaResponse,
)


class AuditoriaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AuditoriaRepository(db)

    @staticmethod
    def registrar(
        db: Session,
        actor: Usuario,
        accion: str,
        entidad_tipo: str,
        entidad_id: int | None,
        descripcion: str,
        antes: dict[str, Any] | None = None,
        despues: dict[str, Any] | None = None,
    ) -> RegistroAuditoria:
        evento = RegistroAuditoria(
            actor_id=actor.id,
            actor_username=actor.username,
            actor_rol=str(actor.rol),
            accion=accion,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            descripcion=descripcion,
            antes=antes,
            despues=despues,
        )
        db.add(evento)
        return evento

    def listar(
        self,
        desde: date | None,
        hasta: date | None,
        limit: int,
        offset: int,
    ) -> AuditoriaPageResponse:
        rows, total = self.repository.listar(desde, hasta, limit, offset)
        return AuditoriaPageResponse(
            items=[RegistroAuditoriaResponse.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )