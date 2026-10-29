"""Gestión de permisos funcionales por usuario."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permisos import (
    ADMINISTRADOR,
    CLAVES_PERMISOS,
    GRUPOS,
    PERMISOS,
    PERMISOS_POR_CLAVE,
    es_critico,
    normalizar_solicitud,
    permisos_efectivos,
    permisos_por_defecto,
    tiene_permiso,
)
from app.models.personal import Usuario
from app.schemas.permiso import (
    ActualizarPermisosRequest,
    CatalogoPermisosResponse,
    PermisoItem,
    PermisosUsuarioResponse,
)
from app.services.auditoria_service import AuditoriaService


class PermisoService:
    """Lee y actualiza los overrides de permisos de un usuario."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _obtener_usuario(self, usuario_id: int) -> Usuario:
        usuario = self.db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        return usuario

    def _motivo_bloqueo(self, objetivo: Usuario, actor: Usuario) -> str | None:
        if objetivo.id == actor.id:
            return "No puedes modificar tus propios permisos."
        if objetivo.rol == ADMINISTRADOR:
            return "El Administrador conserva siempre todos los permisos."
        if not tiene_permiso(actor, "permisos_gestionar"):
            return "No tienes permiso para gestionar permisos."
        return None

    def _items(
        self,
        objetivo: Usuario,
        actor: Usuario,
        puede_editar: bool,
    ) -> list[PermisoItem]:
        por_defecto = set(permisos_por_defecto(objetivo.rol))
        efectivos = set(permisos_efectivos(objetivo))
        actor_es_admin = actor.rol == ADMINISTRADOR
        return [
            PermisoItem(
                clave=permiso["clave"],
                nombre=permiso["nombre"],
                descripcion=permiso["descripcion"],
                grupo=permiso["grupo"],
                critico=bool(permiso["critico"]),
                por_defecto=permiso["clave"] in por_defecto,
                concedido=permiso["clave"] in efectivos,
                editable=puede_editar
                and (actor_es_admin or not permiso["critico"]),
            )
            for permiso in PERMISOS
        ]

    def catalogo(self, actor: Usuario) -> CatalogoPermisosResponse:
        """Catálogo completo referido al usuario en sesión."""
        return CatalogoPermisosResponse(
            grupos=list(GRUPOS),
            permisos=self._items(actor, actor, puede_editar=False),
        )

    def obtener(self, usuario_id: int, actor: Usuario) -> PermisosUsuarioResponse:
        objetivo = self._obtener_usuario(usuario_id)
        motivo = self._motivo_bloqueo(objetivo, actor)
        puede_editar = motivo is None
        return PermisosUsuarioResponse(
            usuario_id=objetivo.id,
            username=objetivo.username,
            rol=objetivo.rol,
            es_administrador=objetivo.rol == ADMINISTRADOR,
            es_usuario_actual=objetivo.id == actor.id,
            puede_editar=puede_editar,
            motivo_bloqueo=motivo,
            grupos=list(GRUPOS),
            permisos=self._items(objetivo, actor, puede_editar),
        )

    def actualizar(
        self,
        usuario_id: int,
        request: ActualizarPermisosRequest,
        actor: Usuario,
    ) -> PermisosUsuarioResponse:
        objetivo = self._obtener_usuario(usuario_id)

        motivo = self._motivo_bloqueo(objetivo, actor)
        if motivo is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=motivo,
            )

        desconocidos = [
            clave for clave in request.permisos if clave not in PERMISOS_POR_CLAVE
        ]
        if desconocidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Permiso desconocido: "
                    + ", ".join(sorted(set(desconocidos)))
                ),
            )

        solicitados = set(normalizar_solicitud(request.permisos))
        actuales = set(permisos_efectivos(objetivo))

        if actor.rol != ADMINISTRADOR:
            criticos = {
                clave for clave in CLAVES_PERMISOS if es_critico(clave)
            }
            if (solicitados & criticos) != (actuales & criticos):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Solo un Administrador puede cambiar los permisos "
                        "críticos (personal, permisos, auditoría y copias)."
                    ),
                )

        por_defecto = set(permisos_por_defecto(objetivo.rol))
        overrides: dict[str, Any] = {
            clave: clave in solicitados
            for clave in CLAVES_PERMISOS
            if (clave in solicitados) != (clave in por_defecto)
        }

        antes = {"permisos": sorted(actuales)}
        objetivo.permisos = overrides or None
        despues = {"permisos": sorted(permisos_efectivos(objetivo))}

        AuditoriaService.registrar(
            self.db,
            actor,
            "PERMISOS_ACTUALIZADOS",
            "usuario",
            objetivo.id,
            f"Permisos de {objetivo.username} actualizados",
            antes=antes,
            despues=despues,
        )
        self.db.commit()
        self.db.refresh(objetivo)

        return self.obtener(objetivo.id, actor)
