"""Autorización, conexión WebRTC y almacenamiento persistente de clips."""

import base64
import hashlib
import hmac
import json
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import crear_access_token, decodificar_access_token
from app.models.camera import Camera, CameraAccess, CameraClip
from app.models.personal import Usuario
from app.schemas.camera import (
    CameraAccessUpdate,
    CameraCreate,
    CameraUpdate,
)
from app.schemas.personal import RolEnum

logger = logging.getLogger(__name__)
CAMERA_STREAM_TOKEN_SECONDS = 300
CAMERA_CLIP_RETENTION_DAYS = 7
CAMERA_CLIP_ABANDONED_HOURS = 24
CAMERA_CHUNK_MAX_BYTES = 16 * 1024 * 1024
CAMERA_MIN_FREE_BYTES = 512 * 1024 * 1024


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CameraService:
    """Aplica permisos de cámaras y gestiona metadatos y archivos de clips.

    La dependencia de la API proporciona la sesión. Las credenciales RTSP no
    pertenecen a este servicio: los streams solo se publican por el puente
    WebRTC configurado.
    """

    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    @staticmethod
    def _es_gestor(usuario: Usuario) -> bool:
        return usuario.rol in {
            RolEnum.ADMINISTRADOR.value,
            RolEnum.GERENTE.value,
        }

    def _storage_dir(self) -> Path:
        return Path(self.settings.CAMERA_STORAGE_DIR).expanduser().resolve()

    def _ensure_storage(self) -> Path:
        storage_dir = self._storage_dir()
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    def _stream_url(self, slug: str) -> str | None:
        base_url = self.settings.CAMERA_BRIDGE_BASE_URL.strip().rstrip("/")
        if not base_url:
            return None
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            and not (
                parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        ) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CAMERA_BRIDGE_BASE_URL debe usar HTTPS y no incluir credenciales",
            )
        if parsed.path not in {"", "/"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CAMERA_BRIDGE_BASE_URL debe ser el origen del puente, sin ruta",
            )
        return f"{base_url}/{slug}/whep"

    def _camera_or_404(self, camera_id: int, require_active: bool = True) -> Camera:
        camera = self.db.get(Camera, camera_id)
        if not camera or (require_active and not camera.activa):
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        return camera

    def require_access(
        self, camera: Camera, usuario: Usuario
    ) -> None:
        """Oculta cámaras sin permiso o a usuarios inactivos."""
        if self._es_gestor(usuario):
            return
        access = self.db.get(CameraAccess, (camera.id, usuario.id))
        if not usuario.activo or not access:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")

    def _response(self, camera: Camera, viewer_ids: list[int] | None = None) -> dict[str, Any]:
        return {
            "id": camera.id,
            "nombre": camera.nombre,
            "slug": camera.slug,
            "activa": camera.activa,
            "stream_url": self._stream_url(camera.slug),
            "usuario_ids": viewer_ids or [],
        }

    def listar_camaras(self, usuario: Usuario) -> list[dict[str, Any]]:
        """Devuelve todas las cámaras a gerentes y solo las autorizadas al resto."""
        if self._es_gestor(usuario):
            cameras = self.db.execute(
                select(Camera).order_by(Camera.nombre, Camera.id)
            ).scalars().all()
            access_rows = self.db.execute(
                select(CameraAccess.camara_id, CameraAccess.usuario_id)
            ).all()
            access_by_camera: dict[int, list[int]] = {}
            for camera_id, user_id in access_rows:
                access_by_camera.setdefault(camera_id, []).append(user_id)
            return [
                self._response(camera, access_by_camera.get(camera.id, []))
                for camera in cameras
            ]

        cameras = self.db.execute(
            select(Camera)
            .join(CameraAccess, CameraAccess.camara_id == Camera.id)
            .where(
                CameraAccess.usuario_id == usuario.id,
            )
            .order_by(Camera.nombre, Camera.id)
        ).scalars().all()
        return [self._response(camera) for camera in cameras]

    def listar_usuarios_autorizables(self) -> list[dict[str, Any]]:
        """Lista vendedores activos elegibles para recibir acceso."""
        users = self.db.execute(
            select(Usuario)
            .where(
                Usuario.activo.is_(True),
                Usuario.rol == RolEnum.VENDEDOR.value,
            )
            .order_by(Usuario.username)
        ).scalars().all()
        return [
            {
                "id": user.id,
                "username": user.username,
                "nombre_completo": (
                    f"{user.empleado.nombre} {user.empleado.apellido}".strip()
                ),
            }
            for user in users
        ]

    def crear_camara(self, datos: CameraCreate) -> dict[str, Any]:
        """Crea una ruta y convierte identificadores duplicados en HTTP 409."""
        camera = Camera(nombre=datos.nombre, slug=datos.slug, activa=True)
        self.db.add(camera)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Ya existe una cámara con ese identificador",
            ) from exc
        self.db.refresh(camera)
        return self._response(camera)

    def actualizar_camara(
        self, camera_id: int, datos: CameraUpdate
    ) -> dict[str, Any]:
        """Actualiza metadatos sin modificar el historial de clips."""
        camera = self._camera_or_404(camera_id, require_active=False)
        updates = datos.model_dump(exclude_unset=True)
        new_slug = updates.get("slug")
        if new_slug and new_slug != camera.slug:
            duplicate = self.db.execute(
                select(Camera.id).where(
                    Camera.slug == new_slug,
                    Camera.id != camera.id,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cámara con ese identificador",
                )
        for field, value in updates.items():
            setattr(camera, field, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Ya existe una cámara con ese identificador",
            ) from exc
        self.db.refresh(camera)
        return self._response(camera)

    def actualizar_accesos(
        self, camera_id: int, datos: CameraAccessUpdate
    ) -> dict[str, Any]:
        """Reemplaza permisos tras validar que cada vendedor esté activo."""
        camera = self._camera_or_404(camera_id, require_active=False)
        user_ids = set(datos.usuario_ids)
        users = self.db.execute(
            select(Usuario).where(
                Usuario.id.in_(user_ids) if user_ids else False,
                Usuario.activo.is_(True),
                Usuario.rol == RolEnum.VENDEDOR.value,
            )
        ).scalars().all()
        if {user.id for user in users} != user_ids:
            raise HTTPException(
                status_code=400,
                detail="Solo se puede autorizar a vendedores activos",
            )

        self.db.execute(
            delete(CameraAccess).where(CameraAccess.camara_id == camera.id)
        )
        self.db.add_all(
            CameraAccess(camara_id=camera.id, usuario_id=user_id)
            for user_id in user_ids
        )
        self.db.commit()
        return self._response(camera, sorted(user_ids))

    def emitir_token_stream(
        self, camera_id: int, usuario: Usuario
    ) -> dict[str, Any]:
        """Emite un JWT de cinco minutos limitado a una cámara y solo lectura."""
        camera = self._camera_or_404(camera_id)
        self.require_access(camera, usuario)
        stream_url = self._stream_url(camera.slug)
        if not stream_url:
            raise HTTPException(
                status_code=503,
                detail="El puente de cámaras todavía no está configurado",
            )
        ice_servers = self._ice_servers(usuario.id)
        token = crear_access_token(
            {
                "sub": str(usuario.id),
                "purpose": "camera_stream",
                "camera_slug": camera.slug,
            },
            expires_delta=timedelta(seconds=CAMERA_STREAM_TOKEN_SECONDS),
        )
        return {
            "token": token,
            "expira_en_segundos": CAMERA_STREAM_TOKEN_SECONDS,
            "ice_servers": ice_servers,
        }

    @staticmethod
    def _valid_ice_server(server: Any) -> bool:
        if not isinstance(server, dict):
            return False
        if "username" in server or "credential" in server:
            return False
        urls = server.get("urls")
        url_list = [urls] if isinstance(urls, str) else urls
        if (
            not isinstance(url_list, list)
            or not url_list
            or any(
                not isinstance(url, str)
                or not url.startswith(("stun:", "stuns:", "turn:", "turns:"))
                for url in url_list
            )
        ):
            return False
        return True

    def _ice_servers(self, usuario_id: int) -> list[dict[str, Any]]:
        """Valida ICE y genera credenciales Coturn temporales cuando se requieren."""
        try:
            configured = json.loads(self.settings.CAMERA_ICE_SERVERS_JSON)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=503,
                detail="CAMERA_ICE_SERVERS_JSON no contiene JSON válido",
            ) from exc
        if (
            not isinstance(configured, list)
            or any(not self._valid_ice_server(server) for server in configured)
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    "CAMERA_ICE_SERVERS_JSON debe ser una lista de URLs STUN/TURN "
                    "sin credenciales permanentes"
                ),
            )

        has_turn = any(
            url.startswith(("turn:", "turns:"))
            for server in configured
            for url in (
                [server["urls"]]
                if isinstance(server["urls"], str)
                else server["urls"]
            )
        )
        if not has_turn:
            return configured
        if not self.settings.CAMERA_TURN_SHARED_SECRET:
            raise HTTPException(
                status_code=503,
                detail="CAMERA_TURN_SHARED_SECRET es requerido para servidores TURN",
            )

        username = f"{int(time.time()) + CAMERA_STREAM_TOKEN_SECONDS}:{usuario_id}"
        credential = base64.b64encode(
            hmac.new(
                self.settings.CAMERA_TURN_SHARED_SECRET.encode("utf-8"),
                username.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("ascii")
        return [
            {**server, "username": username, "credential": credential}
            if any(
                url.startswith(("turn:", "turns:"))
                for url in (
                    [server["urls"]]
                    if isinstance(server["urls"], str)
                    else server["urls"]
                )
            )
            else server
            for server in configured
        ]

    def autorizar_puente(
        self,
        camera_slug: str,
        token: str,
        action: str,
        path: str,
    ) -> None:
        """Autoriza lectura de MediaMTX comprobando los permisos vigentes."""
        if action != "read" or path != camera_slug or not token:
            raise HTTPException(status_code=401, detail="No autorizado")
        try:
            payload = decodificar_access_token(token)
        except HTTPException as exc:
            raise HTTPException(status_code=401, detail="No autorizado") from exc
        if (
            payload.get("purpose") != "camera_stream"
            or payload.get("camera_slug") != camera_slug
            or not payload.get("sub")
        ):
            raise HTTPException(status_code=401, detail="No autorizado")
        try:
            usuario_id = int(payload["sub"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="No autorizado") from exc

        camera = self.db.execute(
            select(Camera).where(Camera.slug == camera_slug, Camera.activa.is_(True))
        ).scalar_one_or_none()
        usuario = self.db.get(Usuario, usuario_id)
        if not camera or not usuario or not usuario.activo:
            raise HTTPException(status_code=401, detail="No autorizado")
        if (
            usuario.rol == RolEnum.VENDEDOR.value
            and not usuario.turno_habilitado
        ):
            raise HTTPException(status_code=401, detail="No autorizado")
        try:
            self.require_access(camera, usuario)
        except HTTPException as exc:
            raise HTTPException(status_code=401, detail="No autorizado") from exc

    def _clip_or_404(
        self, clip_id: str, camera_id: int | None = None
    ) -> CameraClip:
        clip = self.db.get(CameraClip, clip_id)
        if not clip or (camera_id is not None and clip.camara_id != camera_id):
            raise HTTPException(status_code=404, detail="Clip no encontrado")
        return clip

    def _clip_path(self, clip: CameraClip) -> Path:
        extension = "webm" if clip.mime_type == "video/webm" else "mp4"
        return self._storage_dir() / f"{clip.id}.{extension}"

    def iniciar_clip(
        self, camera_id: int, usuario: Usuario, mime_type: str
    ) -> dict[str, Any]:
        """Inicia una grabación solo con permiso vigente y espacio suficiente."""
        camera = self._camera_or_404(camera_id)
        self.require_access(camera, usuario)
        if not self._stream_url(camera.slug):
            raise HTTPException(
                status_code=503,
                detail="El puente de cámaras todavía no está configurado",
            )
        normalized_mime = mime_type.split(";", 1)[0].strip().lower()
        if normalized_mime not in {"video/webm", "video/mp4"}:
            raise HTTPException(
                status_code=400, detail="El formato debe ser video/webm o video/mp4"
            )
        storage_dir = self._ensure_storage()
        self._check_storage_space(storage_dir)
        clip_id = str(uuid.uuid4())
        clip = CameraClip(
            id=clip_id,
            camara_id=camera.id,
            usuario_id=usuario.id,
            usuario_nombre=usuario.username,
            mime_type=normalized_mime,
            estado="GRABANDO",
        )
        self._clip_path(clip).touch(exist_ok=False)
        self.db.add(clip)
        self.db.commit()
        return {"id": clip.id}

    @staticmethod
    def _check_storage_space(storage_dir: Path, incoming_bytes: int = 0) -> None:
        available = shutil.disk_usage(storage_dir).free
        if available - incoming_bytes < CAMERA_MIN_FREE_BYTES:
            raise HTTPException(
                status_code=507,
                detail=(
                    "No hay espacio suficiente en el disco de clips. "
                    "Amplíe el disco o elimine clips antes de continuar."
                ),
            )

    def guardar_fragmento(
        self,
        camera_id: int,
        clip_id: str,
        sequence: int,
        usuario: Usuario,
        data: bytes,
    ) -> dict[str, int]:
        """Añade un fragmento secuencial y revierte el archivo si falla la BD."""
        if not data:
            raise HTTPException(status_code=400, detail="El fragmento está vacío")
        if len(data) > CAMERA_CHUNK_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail="El fragmento supera el máximo de 16 MiB",
            )
        camera = self._camera_or_404(camera_id)
        self.require_access(camera, usuario)
        clip = self.db.execute(
            select(CameraClip)
            .where(CameraClip.id == clip_id, CameraClip.camara_id == camera.id)
            .with_for_update()
        ).scalar_one_or_none()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip no encontrado")
        self._require_clip_owner(clip, usuario)
        if clip.estado != "GRABANDO":
            raise HTTPException(status_code=409, detail="El clip ya fue finalizado")
        if sequence != clip.siguiente_fragmento:
            raise HTTPException(
                status_code=409,
                detail="El fragmento está fuera de secuencia; reinicie la grabación",
            )
        storage_dir = self._ensure_storage()
        self._check_storage_space(storage_dir, len(data))
        if sequence == 0 and not self._valid_video_signature(clip.mime_type, data):
            raise HTTPException(status_code=400, detail="El archivo no es un video válido")
        path = self._clip_path(clip)
        if not path.is_file():
            raise HTTPException(
                status_code=409,
                detail="El archivo de grabación no está disponible; inicie otro clip",
            )
        original_size = clip.bytes_guardados
        actual_size = path.stat().st_size
        if actual_size < original_size:
            raise HTTPException(
                status_code=409,
                detail="El archivo de grabación está incompleto; inicie otro clip",
            )
        if actual_size > original_size:
            with path.open("r+b") as file:
                file.truncate(original_size)
        with path.open("r+b") as file:
            file.seek(original_size)
            file.write(data)
        clip.bytes_guardados += len(data)
        clip.siguiente_fragmento += 1
        clip.actualizado_en = _utc_now_naive()
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            try:
                with path.open("r+b") as file:
                    file.truncate(original_size)
            except OSError as exc:
                logger.exception(
                    "No se pudo revertir el fragmento fallido del clip %s",
                    clip_id,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Falló la escritura del clip y no se pudo revertir el archivo",
                ) from exc
            raise
        return {"fragmentos_recibidos": clip.siguiente_fragmento}

    @staticmethod
    def _valid_video_signature(mime_type: str, data: bytes) -> bool:
        if mime_type == "video/webm":
            return data.startswith(bytes.fromhex("1a45dfa3"))
        return len(data) >= 8 and data[4:8] == b"ftyp"

    @staticmethod
    def _require_clip_owner(clip: CameraClip, usuario: Usuario) -> None:
        if not CameraService._es_gestor(usuario) and clip.usuario_id != usuario.id:
            raise HTTPException(status_code=404, detail="Clip no encontrado")

    def finalizar_clip(
        self, camera_id: int, clip_id: str, usuario: Usuario
    ) -> dict[str, Any]:
        """Finaliza una grabación que contiene video."""
        camera = self._camera_or_404(camera_id, require_active=False)
        self.require_access(camera, usuario)
        clip = self.db.execute(
            select(CameraClip)
            .where(CameraClip.id == clip_id, CameraClip.camara_id == camera.id)
            .with_for_update()
        ).scalar_one_or_none()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip no encontrado")
        self._require_clip_owner(clip, usuario)
        if clip.estado != "GRABANDO":
            raise HTTPException(status_code=409, detail="El clip ya fue finalizado")
        if clip.bytes_guardados == 0:
            raise HTTPException(status_code=400, detail="El clip no contiene video")
        clip.estado = "COMPLETADO"
        clip.finalizado_en = _utc_now_naive()
        clip.actualizado_en = clip.finalizado_en
        self.db.commit()
        return self._clip_response(clip, camera.nombre)

    def cancelar_clip(
        self, clip_id: str, usuario: Usuario, camera_id: int | None = None
    ) -> None:
        """Elimina una grabación propia tras volver a comprobar el permiso."""
        clip = self._clip_or_404(clip_id, camera_id)
        camera = self._camera_or_404(clip.camara_id, require_active=False)
        self.require_access(camera, usuario)
        self._require_clip_owner(clip, usuario)
        path = self._clip_path(clip)
        if path.exists():
            path.unlink()
        self.db.delete(clip)
        self.db.commit()

    @staticmethod
    def _clip_response(clip: CameraClip, camera_name: str) -> dict[str, Any]:
        return {
            "id": clip.id,
            "camara_id": clip.camara_id,
            "camara_nombre": camera_name,
            "usuario_nombre": clip.usuario_nombre,
            "mime_type": clip.mime_type,
            "bytes_guardados": clip.bytes_guardados,
            "creado_en": clip.creado_en,
            "finalizado_en": clip.finalizado_en,
        }

    def listar_clips(self, usuario: Usuario) -> list[dict[str, Any]]:
        """Lista clips completos solo de cámaras accesibles en este momento."""
        camera_query = select(Camera.id, Camera.nombre)
        if not self._es_gestor(usuario):
            camera_query = camera_query.join(
                CameraAccess, CameraAccess.camara_id == Camera.id
            ).where(CameraAccess.usuario_id == usuario.id)
        allowed_cameras = {
            camera_id: name
            for camera_id, name in self.db.execute(camera_query).all()
        }
        if not allowed_cameras:
            return []
        clips = self.db.execute(
            select(CameraClip)
            .where(
                CameraClip.camara_id.in_(allowed_cameras),
                CameraClip.estado == "COMPLETADO",
            )
            .order_by(CameraClip.creado_en.desc())
        ).scalars().all()
        return [
            self._clip_response(clip, allowed_cameras[clip.camara_id])
            for clip in clips
        ]

    def obtener_video_clip(self, clip_id: str, usuario: Usuario) -> tuple[Path, str]:
        """Devuelve la ruta privada del clip completo tras validar el acceso."""
        clip = self._clip_or_404(clip_id)
        camera = self._camera_or_404(clip.camara_id, require_active=False)
        self.require_access(camera, usuario)
        if clip.estado != "COMPLETADO":
            raise HTTPException(status_code=404, detail="Clip no encontrado")
        path = self._clip_path(clip)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="El archivo del clip no existe")
        return path, clip.mime_type

    def resumen_almacenamiento(self) -> dict[str, int]:
        """Resume clips y capacidad del disco para diagnóstico de gerencia."""
        storage_dir = self._ensure_storage()
        usage = shutil.disk_usage(storage_dir)
        clips, bytes_used = self.db.execute(
            select(
                func.count(CameraClip.id),
                func.coalesce(func.sum(CameraClip.bytes_guardados), 0),
            ).where(
                CameraClip.estado == "COMPLETADO"
            )
        ).one()
        return {
            "clips": clips,
            "bytes_usados": bytes_used,
            "bytes_libres": usage.free,
            "bytes_totales": usage.total,
        }

    def limpiar_clips_vencidos(self) -> int:
        """Elimina clips vencidos y cargas abandonadas."""
        now = _utc_now_naive()
        expired_before = now - timedelta(days=CAMERA_CLIP_RETENTION_DAYS)
        abandoned_before = now - timedelta(hours=CAMERA_CLIP_ABANDONED_HOURS)
        expired = self.db.execute(
            select(CameraClip).where(
                or_(
                    (
                        (CameraClip.estado == "COMPLETADO")
                        & (CameraClip.creado_en < expired_before)
                    ),
                    (CameraClip.estado == "GRABANDO")
                    & (CameraClip.actualizado_en < abandoned_before),
                )
            )
        ).scalars().all()
        deleted = 0
        for clip in expired:
            try:
                path = self._clip_path(clip)
                if path.exists():
                    path.unlink()
            except OSError:
                logger.exception("No se pudo eliminar el archivo del clip %s", clip.id)
                continue
            self.db.delete(clip)
            self.db.commit()
            deleted += 1
        return deleted
