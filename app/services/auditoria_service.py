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
    """Registra y consulta eventos de auditoría del sistema."""

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
        """Agrega un evento de auditoría a la sesión sin confirmarlo.

        Args:
            db: Sesión de base de datos.
            actor: Usuario que ejecuta la acción.
            accion: Identificador de la acción realizada.
            entidad_tipo: Tipo de entidad afectada.
            entidad_id: ID de la entidad afectada (puede ser None).
            descripcion: Descripción legible del evento.
            antes: Estado previo de la entidad (opcional).
            despues: Estado posterior de la entidad (opcional).

        Returns:
            El registro de auditoría construido (aún sin commit).
        """
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
        """Devuelve eventos de auditoría paginados y filtrados por rango de fechas.

        Args:
            desde: Fecha inicial del filtro (opcional).
            hasta: Fecha final del filtro (opcional).
            limit: Cantidad máxima de registros a devolver.
            offset: Desplazamiento para la paginación.

        Returns:
            AuditoriaPageResponse con los items y el total de registros.
        """
        rows, total = self.repository.listar(desde, hasta, limit, offset)
        return AuditoriaPageResponse(
            items=[RegistroAuditoriaResponse.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )