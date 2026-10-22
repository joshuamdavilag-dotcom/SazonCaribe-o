"""Notificaciones push (Web Push / VAPID) para comandas de cocina y salón.

Dos flujos:

- El mesero manda una comanda → se avisa a quien tenga activos los avisos
  de cocina (``Usuario.avisos_cocina``).
- La cocina marca la comanda como lista → se avisa al mesero que la creó
  (si tiene activos sus avisos de mesero) y a quien pidió verlas todas.

Los avisos son opt-in por usuario: nadie recibe nada que no haya activado en
su panel de notificaciones (la suscripción del dispositivo sigue siendo el
permiso maestro). Se entregan "fuera del sistema": basta con que la cuenta
siga vigente (usuario y empleado activos) y que el dispositivo tenga la
suscripción registrada. Cada usuario puede limitar los avisos a su turno
activo con ``Usuario.avisos_fuera_de_turno = False``.

Los envíos se ejecutan como tarea en segundo plano para no bloquear ni
alterar el flujo de las órdenes. Si el push falla, la orden nunca se ve
afectada: el error queda en el log y la suscripción caduca se elimina.
"""

import json
import logging
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.vapid import clave_privada_vapid
from app.models.asistencia import Asistencia
from app.models.orden import Orden
from app.models.personal import Empleado, Usuario
from app.models.push import PushSuscripcion
from app.schemas.personal import RolEnum

logger = logging.getLogger(__name__)

try:
    from pywebpush import WebPushException, webpush

    PUSH_DISPONIBLE = True
except Exception:  # pragma: no cover - dependencia opcional en tiempo de import
    webpush = None

    class WebPushException(Exception):  # type: ignore[no-redef]
        pass

    PUSH_DISPONIBLE = False

KEYWORDS_PUESTO_COCINA = ("cocin", "cosin", "chef")

RUTA_APP = "/Templates/index.html"

CAMPOS_PREFERENCIAS_AVISOS = (
    "avisos_fuera_de_turno",
    "avisos_cocina",
    "avisos_mesero",
    "avisos_mesero_todas",
)


def aplicar_preferencias_avisos(usuario: Usuario, cambios) -> None:
    """Aplica un cambio parcial de preferencias de avisos al usuario.

    Solo escribe los campos presentes en ``cambios`` (los demás conservan su
    valor). ``avisos_mesero_todas`` no tiene sentido sin los avisos de mesero,
    así que se apaga junto con ellos.
    """
    for campo in CAMPOS_PREFERENCIAS_AVISOS:
        valor = getattr(cambios, campo, None)
        if valor is not None:
            setattr(usuario, campo, bool(valor))
    if not usuario.avisos_mesero:
        usuario.avisos_mesero_todas = False


def es_puesto_cocina(nombre_puesto: Optional[str]) -> bool:
    """Indica si un puesto corresponde a la persona de cocina."""
    if not nombre_puesto:
        return False
    texto = nombre_puesto.strip().lower()
    return any(keyword in texto for keyword in KEYWORDS_PUESTO_COCINA)


def _descripcion_mesa(orden: Orden) -> str:
    if orden.mesa is not None:
        numero = orden.mesa.numero
        return f"Mesa {numero}"
    if orden.nombre_cliente:
        return f"Para llevar · {orden.nombre_cliente}"
    return "Para llevar"


class PushService:
    """Gestiona suscripciones y envíos de notificaciones push."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Suscripciones
    # ------------------------------------------------------------------ #
    def registrar_suscripcion(
        self,
        usuario: Usuario,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: Optional[str] = None,
    ) -> PushSuscripcion:
        """Registra (o actualiza) la suscripción del dispositivo."""
        existente = self.db.execute(
            select(PushSuscripcion).where(PushSuscripcion.endpoint == endpoint)
        ).scalars().first()

        if existente is not None:
            existente.usuario_id = usuario.id
            existente.p256dh = p256dh
            existente.auth = auth
            existente.user_agent = user_agent
        else:
            existente = PushSuscripcion(
                usuario_id=usuario.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent,
            )
            self.db.add(existente)

        self.db.commit()
        self.db.refresh(existente)
        return existente

    def eliminar_suscripcion(self, usuario: Usuario, endpoint: str) -> bool:
        """Elimina la suscripción del dispositivo indicado."""
        suscripcion = self.db.execute(
            select(PushSuscripcion).where(
                PushSuscripcion.endpoint == endpoint,
                PushSuscripcion.usuario_id == usuario.id,
            )
        ).scalars().first()
        if suscripcion is None:
            return False
        self.db.delete(suscripcion)
        self.db.commit()
        return True

    def listar_suscripciones(self, usuario: Usuario) -> list[PushSuscripcion]:
        """Lista los dispositivos suscritos por el usuario."""
        return list(
            self.db.execute(
                select(PushSuscripcion)
                .where(PushSuscripcion.usuario_id == usuario.id)
                .order_by(PushSuscripcion.creada_en.desc())
            ).scalars().all()
        )

    def eliminar_suscripcion_por_id(self, usuario: Usuario, suscripcion_id: int) -> bool:
        """Elimina una suscripción propia por su identificador."""
        suscripcion = self.db.execute(
            select(PushSuscripcion).where(
                PushSuscripcion.id == suscripcion_id,
                PushSuscripcion.usuario_id == usuario.id,
            )
        ).scalars().first()
        if suscripcion is None:
            return False
        self.db.delete(suscripcion)
        self.db.commit()
        return True

    # ------------------------------------------------------------------ #
    #  Destinatarios
    # ------------------------------------------------------------------ #
    def usuarios_avisos_cocina(self) -> list[int]:
        """Usuarios activos suscritos a los avisos de comandas nuevas.

        Ya no depende del puesto: cualquier usuario (dueño, programador,
        mesero) puede activar los avisos de cocina desde su panel.
        """
        return list(
            self.db.execute(
                select(Usuario.id)
                .join(Empleado, Usuario.empleado_id == Empleado.id)
                .where(
                    Usuario.avisos_cocina.is_(True),
                    Usuario.activo.is_(True),
                    Empleado.activo.is_(True),
                )
            ).scalars().all()
        )

    def usuarios_avisos_mesero_todas(self) -> list[int]:
        """Usuarios activos que quieren las comandas listas de todos los meseros."""
        return list(
            self.db.execute(
                select(Usuario.id)
                .join(Empleado, Usuario.empleado_id == Empleado.id)
                .where(
                    Usuario.avisos_mesero.is_(True),
                    Usuario.avisos_mesero_todas.is_(True),
                    Usuario.activo.is_(True),
                    Empleado.activo.is_(True),
                )
            ).scalars().all()
        )

    def usuarios_con_avisos_mesero(self, usuario_ids: Iterable[int]) -> list[int]:
        """Filtra los IDs dados a quienes tienen activos los avisos de mesero."""
        ids = [usuario_id for usuario_id in usuario_ids if usuario_id]
        if not ids:
            return []
        return list(
            self.db.execute(
                select(Usuario.id).where(
                    Usuario.id.in_(ids),
                    Usuario.avisos_mesero.is_(True),
                )
            ).scalars().all()
        )

    def usuarios_administracion(self) -> list[int]:
        """Usuarios activos con rol Administrador o Gerente."""
        return list(
            self.db.execute(
                select(Usuario.id)
                .join(Empleado, Usuario.empleado_id == Empleado.id)
                .where(
                    Usuario.rol.in_([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]),
                    Usuario.activo.is_(True),
                    Empleado.activo.is_(True),
                )
            ).scalars().all()
        )

    def usuarios_reciben_avisos(self, usuario_ids: Iterable[int]) -> list[int]:
        """Usuarios que pueden recibir los avisos push.

        La entrega ya NO exige un turno abierto: el aviso llega siempre que
        la cuenta siga vigente (usuario y empleado activos) y el dispositivo
        tenga la suscripción registrada. Así se puede recibir la
        notificación "fuera del sistema" (turno cerrado, app cerrada o
        navegador sin sesión iniciada).

        Cada usuario puede pedir explícitamente lo contrario con
        ``Usuario.avisos_fuera_de_turno = False``: en ese caso solo recibe
        avisos mientras tiene el turno abierto.
        """
        ids = [usuario_id for usuario_id in usuario_ids if usuario_id]
        if not ids:
            return []

        filas = self.db.execute(
            select(
                Usuario.id,
                Usuario.rol,
                Usuario.turno_habilitado,
                Usuario.avisos_fuera_de_turno,
            )
            .join(Empleado, Usuario.empleado_id == Empleado.id)
            .where(
                Usuario.id.in_(ids),
                Usuario.activo.is_(True),
                Empleado.activo.is_(True),
            )
        ).all()

        turnos_abiertos = set(
            self.db.execute(
                select(Usuario.id)
                .join(Empleado, Usuario.empleado_id == Empleado.id)
                .join(Asistencia, Asistencia.empleado_id == Empleado.id)
                .where(
                    Usuario.id.in_(ids),
                    Usuario.activo.is_(True),
                    Empleado.activo.is_(True),
                    Asistencia.hora_salida_real.is_(None),
                    Asistencia.anulada.is_(False),
                )
            )
            .scalars()
            .all()
        )

        destinatarios = set()
        for usuario_id, rol, turno_habilitado, avisos_fuera_de_turno in filas:
            if rol == RolEnum.VENDEDOR and not turno_habilitado:
                continue
            if avisos_fuera_de_turno or usuario_id in turnos_abiertos:
                destinatarios.add(usuario_id)
        return sorted(destinatarios)

    # ------------------------------------------------------------------ #
    #  Envío
    # ------------------------------------------------------------------ #
    def enviar(
        self,
        usuario_ids: Iterable[int],
        titulo: str,
        cuerpo: str,
        url: Optional[str] = None,
        tag: Optional[str] = None,
        datos: Optional[dict] = None,
    ) -> int:
        """Envía una notificación a los dispositivos de los usuarios dados."""
        if not PUSH_DISPONIBLE:
            logger.warning("[PUSH] Dependencia pywebpush no disponible; no se envió la notificación")
            return 0

        destinatarios = {usuario_id for usuario_id in usuario_ids if usuario_id}
        if not destinatarios:
            return 0

        privada = clave_privada_vapid()
        if not privada:
            return 0
        suscripciones = list(
            self.db.execute(
                select(PushSuscripcion).where(
                    PushSuscripcion.usuario_id.in_(destinatarios)
                )
            ).scalars().all()
        )
        if not suscripciones:
            return 0

        settings = get_settings()
        payload: dict = {"title": titulo, "body": cuerpo}
        if url:
            payload["url"] = url
        if tag:
            payload["tag"] = tag
        if datos:
            payload["data"] = datos
        cuerpo_json = json.dumps(payload, ensure_ascii=False)

        enviados = 0
        for suscripcion in suscripciones:
            try:
                webpush(
                    subscription_info={
                        "endpoint": suscripcion.endpoint,
                        "keys": {
                            "p256dh": suscripcion.p256dh,
                            "auth": suscripcion.auth,
                        },
                    },
                    data=cuerpo_json,
                    vapid_private_key=privada,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                    ttl=settings.PUSH_TTL,
                    timeout=settings.PUSH_TIMEOUT,
                )
                suscripcion.ultimo_envio_en = datetime.now()
                enviados += 1
            except WebPushException as error:
                codigo = getattr(getattr(error, "response", None), "status_code", None)
                if codigo in (404, 410):
                    logger.info(
                        "[PUSH] Suscripción caducada (HTTP %s) — se elimina", codigo
                    )
                    self.db.delete(suscripcion)
                else:
                    logger.warning(
                        "[PUSH] Error enviando al usuario %s: %s",
                        suscripcion.usuario_id,
                        error,
                    )
            except Exception as error:
                logger.warning(
                    "[PUSH] Fallo inesperado enviando al usuario %s: %s",
                    suscripcion.usuario_id,
                    error,
                )

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
        return enviados

    # ------------------------------------------------------------------ #
    #  Flujos de comanda
    # ------------------------------------------------------------------ #
    def notificar_nueva_comanda(self, orden: Orden) -> int:
        """Avisa a quien tenga activados los avisos de cocina (aunque no tenga turno)."""
        candidatos = [
            usuario_id
            for usuario_id in self.usuarios_avisos_cocina()
            if usuario_id != orden.mesero_id
        ]
        destinatarios = self.usuarios_reciben_avisos(candidatos)
        if not destinatarios:
            return 0

        mesa = _descripcion_mesa(orden)
        articulos = len(orden.detalles or [])
        total = f"C${float(orden.total):,.2f}"
        return self.enviar(
            usuario_ids=destinatarios,
            titulo=f"Nueva comanda #{orden.id} · {mesa}",
            cuerpo=f"{articulos} artículo{'s' if articulos != 1 else ''} · {total}",
            url=f"{RUTA_APP}?pantalla=comandero",
            tag=f"comanda-{orden.id}",
            datos={"orden_id": orden.id, "tipo": "nueva_comanda"},
        )

    def notificar_comanda_lista(self, orden: Orden) -> int:
        """Avisa que la comanda ya está lista (aunque el destinatario no tenga turno).

        Reciben el aviso el mesero de la orden (si activó sus avisos de mesero)
        y todos los usuarios que pidieron ver las comandas de todos los meseros.
        """
        candidatos = list(self.usuarios_avisos_mesero_todas())
        candidatos += self.usuarios_con_avisos_mesero([orden.mesero_id])

        destinatarios = self.usuarios_reciben_avisos(candidatos)
        if not destinatarios:
            return 0

        mesa = _descripcion_mesa(orden)
        if orden.mesa_id:
            url = f"{RUTA_APP}?pantalla=salon&mesa={orden.mesa_id}"
        else:
            url = f"{RUTA_APP}?pantalla=salon"

        return self.enviar(
            usuario_ids=destinatarios,
            titulo=f"Comanda #{orden.id} lista · {mesa}",
            cuerpo="La cocina ya la dejó lista para servir.",
            url=url,
            tag=f"comanda-lista-{orden.id}",
            datos={"orden_id": orden.id, "tipo": "comanda_lista"},
        )

    def notificar_estudio_mercado(self, estudio) -> int:
        """Avisa a administración que el estudio de mercado automático está listo."""
        destinatarios = self.usuarios_reciben_avisos(self.usuarios_administracion())
        if not destinatarios:
            return 0

        return self.enviar(
            usuario_ids=destinatarios,
            titulo="Estudio de mercado del mes disponible",
            cuerpo=(
                f"{estudio.titulo or 'Análisis mensual'} · "
                f"{estudio.desde.strftime('%d/%m')} al {estudio.hasta.strftime('%d/%m')}"
            ),
            url=f"{RUTA_APP}?pantalla=estudio-mercado&estudio={estudio.id}",
            tag="estudio-mercado",
            datos={"estudio_id": estudio.id, "tipo": "estudio_mercado"},
        )

    def notificar_estudio_mercado_error(self, estudio) -> int:
        """Avisa a administración que el estudio automático no pudo generarse."""
        destinatarios = self.usuarios_reciben_avisos(self.usuarios_administracion())
        if not destinatarios:
            return 0

        return self.enviar(
            usuario_ids=destinatarios,
            titulo="El estudio de mercado del mes falló",
            cuerpo=(estudio.error or "No se pudo completar el análisis. Revisa la configuración de IA.")[
                :180
            ],
            url=f"{RUTA_APP}?pantalla=estudio-mercado",
            tag="estudio-mercado-error",
            datos={"estudio_id": estudio.id, "tipo": "estudio_mercado_error"},
        )


def ejecutar_notificacion_push(orden_id: int, tipo: str) -> None:
    """Tarea en segundo plano: envía la notificación sin afectar la orden."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        servicio = PushService(db)
        orden = db.get(Orden, orden_id)
        if orden is None:
            return
        if tipo == "nueva_comanda":
            servicio.notificar_nueva_comanda(orden)
        elif tipo == "comanda_lista":
            servicio.notificar_comanda_lista(orden)
    except Exception:
        logger.exception(
            "[PUSH] No se pudo enviar la notificación de la orden %s (%s)",
            orden_id,
            tipo,
        )
    finally:
        db.close()
