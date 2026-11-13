from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria
from app.models.personal import Usuario
from app.repositories.auditoria_repository import AuditoriaRepository
from app.schemas.auditoria import (
    AuditoriaPageResponse,
    EliminarAuditoriaResponse,
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

    @staticmethod
    def registrar_sistema(
        db: Session,
        accion: str,
        entidad_tipo: str,
        entidad_id: int | None,
        descripcion: str,
        antes: dict[str, Any] | None = None,
        despues: dict[str, Any] | None = None,
    ) -> RegistroAuditoria:
        """Agrega un evento de auditoría ejecutado por el sistema (sin actor humano).

        Se usa para los cierres automáticos de turnos: el registro queda visible
        en la bitácora aunque no haya una persona detrás de la acción.

        Args:
            db: Sesión de base de datos.
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
            actor_id=0,
            actor_username="sistema",
            actor_rol="Sistema",
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

    def eliminar_registro(
        self,
        registro_id: int,
        motivo: str,
        actor: Usuario,
    ) -> EliminarAuditoriaResponse:
        """Borra físicamente un registro de la bitácora dejando rastro de la baja.

        El registro desaparece de la base (no es borrado lógico), porque el
        objetivo es sacar del sistema el dato puntual. La acción sí queda
        auditada con un evento ``AUDITORIA_ELIMINADA`` que guarda **solo la
        cabecera** del registro borrado (fecha, actor, acción y entidad), nunca
        su contenido ``antes``/``despues`` ni la descripción.

        Args:
            registro_id: ID del registro a eliminar.
            motivo: Motivo obligatorio de la eliminación.
            actor: Usuario que ejecuta la baja (Administrador).

        Raises:
            HTTPException 400: si el motivo está vacío.
            HTTPException 404: si el registro no existe.
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El motivo de la eliminación es obligatorio.",
            )

        registro = self.repository.obtener_por_id(registro_id)
        if not registro:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el registro de auditoría con ID {registro_id}",
            )

        accion_eliminada = registro.accion
        cabecera: dict[str, Any] = {
            "ocurrido_en": registro.ocurrido_en.isoformat(sep=" ") if registro.ocurrido_en else None,
            "actor_username": registro.actor_username,
            "accion": registro.accion,
            "entidad_tipo": registro.entidad_tipo,
            "entidad_id": registro.entidad_id,
        }

        try:
            with self.db.begin_nested():
                AuditoriaService.registrar(
                    self.db,
                    actor,
                    "AUDITORIA_ELIMINADA",
                    "auditoria",
                    registro.id,
                    (
                        f"Registro de auditoría #{registro.id} "
                        f"({registro.accion} · {registro.actor_username}) eliminado "
                        f"— motivo: {motivo}"
                    ),
                    antes=cabecera,
                    despues={"eliminado": True, "motivo": motivo},
                )
                self.repository.eliminar(registro)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return EliminarAuditoriaResponse(
            id=registro_id,
            eliminado=True,
            motivo=motivo,
            accion_eliminada=accion_eliminada,
        )
