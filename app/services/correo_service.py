"""Servicio del módulo de correos: configuración, render y envío con Brevo."""

import html as html_lib
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.correos import (
    ASUNTO_POR_TIPO,
    HORAS_POR_DEFECTO,
    SECCIONES,
    SECCIONES_POR_CLAVE,
    TIPOS_CORREO,
    TIPOS_EVENTO,
    TIPOS_POR_CLAVE,
    TIPOS_PROGRAMADOS,
    es_sensible,
    normalizar_secciones,
    secciones_disponibles,
    secciones_por_defecto,
)
from app.core.tiempo import ahora_local, hoy_local
from app.models.auditoria import RegistroAuditoria
from app.models.correo import (
    ConfiguracionCorreo,
    DestinatarioCorreo,
    EnvioCorreo,
    EstadoEnvio,
)
from app.repositories.estudio_mercado_repository import EstudioMercadoRepository
from app.repositories.inventario_repository import InsumoRepository

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

PALETA = {
    "azul": "#003366",
    "turquesa": "#2A9D8F",
    "amarillo": "#FFB703",
    "rojo": "#E63946",
    "fondo": "#F8FAFC",
    "texto": "#0f172a",
    "suave": "#64748b",
    "borde": "#e2e8f0",
}


class ErrorEnvioCorreo(Exception):
    """Falla al entregar un correo al proveedor."""


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def email_valido(email: str) -> bool:
    return bool(RE_EMAIL.match(normalizar_email(email)))


def _esc(valor: Any) -> str:
    return html_lib.escape(str(valor if valor is not None else ""))


def _money(valor: Any) -> str:
    try:
        return f"C${float(valor or 0):,.2f}"
    except (TypeError, ValueError):
        return "C$0.00"


def _entero(valor: Any) -> str:
    try:
        return f"{int(valor or 0):,}"
    except (TypeError, ValueError):
        return "0"


def _fecha(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return _esc(valor)


def rango_mes_anterior(referencia: Optional[date] = None) -> tuple[date, date]:
    """Primer y último día del mes anterior."""
    ref = referencia or hoy_local()
    primero_mes = ref.replace(day=1)
    ultimo_anterior = primero_mes - timedelta(days=1)
    return ultimo_anterior.replace(day=1), ultimo_anterior


class CorreoService:
    """Reglas de negocio del módulo de correos."""

    def __init__(self, db: Session, settings: Optional[Settings] = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.estudio_repo = EstudioMercadoRepository(db)
        self.insumo_repo = InsumoRepository(db)

    # ------------------------------------------------------------------ #
    #  Estado del servicio
    # ------------------------------------------------------------------ #
    def habilitado(self) -> bool:
        return bool(
            (self.settings.BREVO_API_KEY or "").strip()
            and (self.settings.CORREO_REMITENTE or "").strip()
        )

    def estado(self) -> dict[str, Any]:
        habilitado = self.habilitado()
        if habilitado:
            mensaje = (
                "Correos habilitados. Los envíos salen desde "
                f"{self.settings.CORREO_REMITENTE}."
            )
        elif not (self.settings.BREVO_API_KEY or "").strip():
            mensaje = (
                "Falta la API key de Brevo (BREVO_API_KEY). El módulo está "
                "visible pero no puede enviar correos."
            )
        else:
            mensaje = (
                "Falta el correo remitente verificado en Brevo "
                "(CORREO_REMITENTE). No se pueden enviar correos."
            )

        def contar(estado: str) -> int:
            return int(
                self.db.execute(
                    select(func.count(EnvioCorreo.id)).where(EnvioCorreo.estado == estado)
                ).scalar()
                or 0
            )

        tipos_activos = int(
            self.db.execute(
                select(func.count(ConfiguracionCorreo.id)).where(
                    ConfiguracionCorreo.activo.is_(True)
                )
            ).scalar()
            or 0
        )
        total_destinatarios = int(
            self.db.execute(
                select(func.count(DestinatarioCorreo.id)).where(
                    DestinatarioCorreo.activo.is_(True)
                )
            ).scalar()
            or 0
        )
        return {
            "habilitado": habilitado,
            "remitente": self.settings.CORREO_REMITENTE or "",
            "remitente_nombre": self.settings.CORREO_REMITENTE_NOMBRE or "",
            "mensaje": mensaje,
            "pendientes": contar(EstadoEnvio.PENDIENTE.value),
            "enviados": contar(EstadoEnvio.ENVIADO.value),
            "errores": contar(EstadoEnvio.ERROR.value),
            "tipos_activos": tipos_activos,
            "total_destinatarios": total_destinatarios,
        }

    # ------------------------------------------------------------------ #
    #  Destinatarios
    # ------------------------------------------------------------------ #
    def listar_destinatarios(self, solo_activos: bool = False) -> list[DestinatarioCorreo]:
        consulta = select(DestinatarioCorreo)
        if solo_activos:
            consulta = consulta.where(DestinatarioCorreo.activo.is_(True))
        return list(
            self.db.execute(
                consulta.order_by(DestinatarioCorreo.nombre, DestinatarioCorreo.id)
            ).scalars()
        )

    def _validar_email_unico(self, email: str, excluir_id: Optional[int] = None) -> None:
        if not email_valido(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El correo '{email}' no tiene un formato válido.",
            )
        consulta = select(DestinatarioCorreo).where(
            func.lower(DestinatarioCorreo.email) == normalizar_email(email)
        )
        if excluir_id is not None:
            consulta = consulta.where(DestinatarioCorreo.id != excluir_id)
            
        if self.db.execute(consulta).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un destinatario con ese correo.",
            )

    def crear_destinatario(self, datos) -> DestinatarioCorreo:
        email = normalizar_email(datos.email)
        self._validar_email_unico(email)
        destinatario = DestinatarioCorreo(
            nombre=datos.nombre.strip(),
            email=email,
            activo=datos.activo,
        )
        self.db.add(destinatario)
        self.db.commit()
        self.db.refresh(destinatario)
        return destinatario

    def actualizar_destinatario(self, destinatario_id: int, datos) -> DestinatarioCorreo:
        destinatario = self.db.get(DestinatarioCorreo, destinatario_id)
        if destinatario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destinatario no encontrado.",
            )
        if datos.email is not None:
            email = normalizar_email(datos.email)
            self._validar_email_unico(email, excluir_id=destinatario_id)
            destinatario.email = email
        if datos.nombre is not None:
            destinatario.nombre = datos.nombre.strip()
        if datos.activo is not None:
            destinatario.activo = datos.activo

        self.db.commit()
        self.db.refresh(destinatario)
        return destinatario

    def eliminar_destinatario(self, destinatario_id: int) -> None:
        destinatario = self.db.get(DestinatarioCorreo, destinatario_id)
        if destinatario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destinatario no encontrado.",
            )
        self.db.delete(destinatario)
        self.db.commit()

    # ------------------------------------------------------------------ #
    #  Configuración por tipo
    # ------------------------------------------------------------------ #
    def sembrar_configuracion(self) -> int:
        """Crea la configuración que falte sin tocar la existente."""
        existentes = {
            tipo
            for (tipo,) in self.db.execute(select(ConfiguracionCorreo.tipo)).all()
        }
        creadas = 0
        for tipo in TIPOS_CORREO:
            if tipo["clave"] in existentes:
                continue
            self.db.add(
                ConfiguracionCorreo(
                    tipo=tipo["clave"],
                    activo=False,
                    secciones=secciones_por_defecto(tipo["clave"]),
                    destinatario_ids=[],
                    hora=HORAS_POR_DEFECTO.get(tipo["clave"], 8),
                )
            )
            creadas += 1
        if creadas:
            self.db.commit()
        return creadas

    def _config(self, tipo: str) -> ConfiguracionCorreo:
        if tipo not in TIPOS_POR_CLAVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de correo desconocido: '{tipo}'.",
            )
        config = self.db.execute(
            select(ConfiguracionCorreo).where(ConfiguracionCorreo.tipo == tipo)
        ).scalar_one_or_none()
        if config is None:
            config = ConfiguracionCorreo(
                tipo=tipo,
                activo=False,
                secciones=secciones_por_defecto(tipo),
                destinatario_ids=[],
                hora=HORAS_POR_DEFECTO.get(tipo, 8),
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config

    @staticmethod
    def _secciones_config(config: ConfiguracionCorreo) -> list[str]:
        disponibles = [s["clave"] for s in secciones_disponibles(config.tipo)]
        guardadas = config.secciones
        if not isinstance(guardadas, list):
            return secciones_por_defecto(config.tipo)
        return [clave for clave in guardadas if clave in disponibles]

    @staticmethod
    def _ids_config(config: ConfiguracionCorreo) -> list[int]:
        if not isinstance(config.destinatario_ids, list):
            return []
        return [int(valor) for valor in config.destinatario_ids if str(valor).isdigit()]

    def configuracion_a_dict(self, config: ConfiguracionCorreo) -> dict[str, Any]:
        tipo = TIPOS_POR_CLAVE.get(config.tipo, {})
        return {
            "tipo": config.tipo,
            "nombre": tipo.get("nombre", config.tipo),
            "descripcion": tipo.get("descripcion", ""),
            "programado": bool(tipo.get("programado")),
            "evento": bool(tipo.get("evento")),
            "activo": config.activo,
            "hora": config.hora,
            "secciones": self._secciones_config(config),
            "secciones_disponibles": secciones_disponibles(config.tipo),
            "destinatario_ids": self._ids_config(config),
            "actualizado_en": config.actualizado_en,
        }

    def listar_configuracion(self) -> list[dict[str, Any]]:
        self.sembrar_configuracion()
        configs = {
            config.tipo: config
            for config in self.db.execute(select(ConfiguracionCorreo)).scalars()
        }
        return [
            self.configuracion_a_dict(configs[tipo["clave"]])
            for tipo in TIPOS_CORREO
            if tipo["clave"] in configs
        ]

    def guardar_configuracion(self, tipo: str, datos) -> dict[str, Any]:
        config = self._config(tipo)

        if datos.secciones is not None:
            validas, invalidas = normalizar_secciones(tipo, datos.secciones)
            if invalidas:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Secciones no disponibles para este correo: "
                        + ", ".join(invalidas)
                    ),
                )
            config.secciones = validas

        if datos.destinatario_ids is not None:
            ids = list(dict.fromkeys(int(valor) for valor in datos.destinatario_ids))
            if ids:
                encontrados = set(
                    self.db.execute(
                        select(DestinatarioCorreo.id).where(DestinatarioCorreo.id.in_(ids))
                    ).scalars()
                )
                faltantes = [valor for valor in ids if valor not in encontrados]
                if faltantes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Destinatarios inexistentes: {faltantes}",
                    )
            config.destinatario_ids = ids

        if datos.activo is not None:
            config.activo = datos.activo
        if datos.hora is not None:
            config.hora = datos.hora

        self.db.commit()
        self.db.refresh(config)
        return self.configuracion_a_dict(config)

    # ------------------------------------------------------------------ #
    #  Rangos y datos
    # ------------------------------------------------------------------ #
    def _rango(
        self,
        tipo: str,
        desde: Optional[date],
        hasta: Optional[date],
    ) -> tuple[date, date]:
        hoy = hoy_local()
        if tipo == "resumen_semanal":
            return hoy - timedelta(days=6), hoy
        if tipo == "resumen_mensual":
            return rango_mes_anterior(hoy)
        if tipo in {"stock_bajo", "auditoria"}:
            return hoy, hoy
        if desde and hasta:
            if desde > hasta:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La fecha inicial no puede ser posterior a la final.",
                )
            return desde, hasta
        if desde:
            return desde, hasta or hoy
        if hasta:
            return hasta, hasta
        return hoy, hoy

    def _seguro(self, funcion, *args, **kwargs) -> Any:
        try:
            return funcion(*args, **kwargs)
        except Exception:
            self.db.rollback()
            return None

    def _datos(self, clave: str, desde: date, hasta: date, referencia_id: Optional[int]) -> Any:
        if clave == "ventas":
            return self._seguro(self.estudio_repo.resumen_ventas, desde, hasta)
        if clave == "metodos_pago":
            return self._seguro(self.estudio_repo.metodos_pago, desde, hasta)
        if clave == "top_platillos":
            datos = self._seguro(self.estudio_repo.productos_vendidos, desde, hasta)
            return (datos or [])[:10]
        if clave == "gastos":
            return self._seguro(self.estudio_repo.gastos_por_categoria, desde, hasta)
        if clave == "inventario":
            return self._seguro(self.insumo_repo.get_bajo_stock_minimo)
        if clave == "nomina":
            return self._seguro(self.estudio_repo.nomina_pagada, desde, hasta)
        if clave == "anulaciones":
            anuladas = self._seguro(self.estudio_repo.ordenes_anuladas, desde, hasta)
            devueltas = self._seguro(self.estudio_repo.devoluciones, desde, hasta)
            return {"anuladas": anuladas or {}, "devoluciones": devueltas or {}}
        if clave == "auditoria":
            return self._seguro(self._registros_auditoria, desde, hasta)
        if clave == "estudio":
            return self._seguro(self._datos_estudio, referencia_id, desde, hasta)
        return None

    def _registros_auditoria(self, desde: date, hasta: date) -> list[RegistroAuditoria]:
        inicio = datetime.combine(desde, datetime.min.time())
        fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
        return list(
            self.db.execute(
                select(RegistroAuditoria)
                .where(
                    RegistroAuditoria.ocurrido_en >= inicio,
                    RegistroAuditoria.ocurrido_en < fin,
                )
                .order_by(RegistroAuditoria.ocurrido_en.desc())
                .limit(30)
            ).scalars()
        )

    def _datos_estudio(
        self,
        referencia_id: Optional[int],
        desde: date,
        hasta: date,
    ) -> Optional[dict[str, Any]]:
        from app.models.estudio_mercado import EstadoEstudio, EstudioMercado

        estudio = None
        if referencia_id:
            estudio = self.db.get(EstudioMercado, referencia_id)
        if estudio is None:
            estudio = self.db.execute(
                select(EstudioMercado)
                .where(EstudioMercado.estado == EstadoEstudio.COMPLETADO)
                .order_by(EstudioMercado.id.desc())
                .limit(1)
            ).scalar_one_or_none()
        if estudio is None:
            return None
        return {
            "titulo": estudio.titulo or "Estudio de mercado",
            "resumen": estudio.resumen or "",
            "fortalezas": estudio.fortalezas or [],
            "debilidades": estudio.debilidades or [],
            "estrategias": estudio.estrategias or [],
            "desde": estudio.desde,
            "hasta": estudio.hasta,
        }

    # ------------------------------------------------------------------ #
    #  Render HTML
    # ------------------------------------------------------------------ #
    @staticmethod
    def _kpis(items: list[tuple[str, str, str]]) -> str:
        celdas = []
        for etiqueta, valor, color in items:
            celdas.append(
                f'<td style="width:50%;padding:6px;">'
                f'<div style="border:1px solid {PALETA["borde"]};border-radius:10px;'
                f'padding:12px 14px;background:{PALETA["fondo"]};">'
                f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;'
                f'color:{PALETA["suave"]};">{_esc(etiqueta)}</div>'
                f'<div style="font-size:20px;font-weight:800;color:{color};margin-top:4px;">'
                f'{_esc(valor)}</div></div></td>'
            )
        filas = "".join(
            f"<tr>{''.join(celdas[i:i + 2])}</tr>" for i in range(0, len(celdas), 2)
        )
        return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{filas}</table>'

    @staticmethod
    def _tabla(cabeceras: list[str], filas: list[list[str]]) -> str:
        if not filas:
            return (
                f'<p style="font-size:13px;color:{PALETA["suave"]};margin:0;">'
                "Sin movimientos en el periodo.</p>"
            )
        th = "".join(
            f'<th align="left" style="padding:8px 10px;font-size:11px;text-transform:uppercase;'
            f'letter-spacing:1px;color:#ffffff;background:{PALETA["azul"]};'
            f'border-bottom:1px solid {PALETA["azul"]};">{_esc(c)}</th>'
            for c in cabeceras
        )
        cuerpo = "".join(
            "<tr>"
            + "".join(
                f'<td style="padding:8px 10px;font-size:13px;color:{PALETA["texto"]};'
                f'border-bottom:1px solid {PALETA["borde"]};">{celda}</td>'
                for celda in fila
            )
            + "</tr>"
            for fila in filas
        )
        return (
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            f'style="border-collapse:collapse;border:1px solid {PALETA["borde"]};'
            f'border-radius:10px;overflow:hidden;">'
            f"<thead><tr>{th}</tr></thead><tbody>{cuerpo}</tbody></table>"
        )

    @staticmethod
    def _bloque(nombre: str, contenido: str, primero: bool = False) -> str:
        margen = "0" if primero else "26px"
        return (
            f'<div style="margin-top:{margen};">'
            f'<h2 style="font-size:15px;font-weight:800;color:{PALETA["azul"]};'
            f'border-left:4px solid {PALETA["turquesa"]};padding-left:10px;margin:0 0 12px;">'
            f"{_esc(nombre)}</h2>{contenido}</div>"
        )

    def _bloque_ventas(self, datos: dict) -> str:
        return self._kpis(
            [
                ("Órdenes cobradas", _entero(datos.get("ordenes")), PALETA["azul"]),
                ("Ingresos", _money(datos.get("ingresos")), PALETA["turquesa"]),
                ("Ticket promedio", _money(datos.get("ticket_promedio")), PALETA["azul"]),
                ("Descuentos", _money(datos.get("descuentos")), PALETA["rojo"]),
            ]
        )

    def _bloque_metodos_pago(self, datos: list[dict]) -> str:
        return self._tabla(
            ["Método", "Órdenes", "Monto"],
            [
                [
                    _esc(fila.get("metodo", "")),
                    _entero(fila.get("ordenes")),
                    _money(fila.get("monto")),
                ]
                for fila in datos
            ],
        )

    def _bloque_top_platillos(self, datos: list[dict]) -> str:
        return self._tabla(
            ["Platillo", "Unidades", "Ingresos"],
            [
                [
                    _esc(fila.get("producto", "")),
                    _entero(fila.get("unidades")),
                    _money(fila.get("ingresos")),
                ]
                for fila in datos
            ],
        )

    def _bloque_gastos(self, datos: list[dict]) -> str:
        return self._tabla(
            ["Categoría", "Movimientos", "Monto"],
            [
                [
                    _esc(fila.get("categoria", "")),
                    _entero(fila.get("movimientos")),
                    _money(fila.get("monto")),
                ]
                for fila in datos
            ],
        )

    def _bloque_inventario(self, datos: list[Any]) -> str:
        filas = []
        for insumo in datos:
            unidad = getattr(getattr(insumo, "unidad_medida_obj", None), "abreviatura", None)
            if not unidad:
                unidad = getattr(getattr(insumo, "unidad_medida_obj", None), "nombre", "")
            filas.append(
                [
                    _esc(insumo.nombre),
                    f"{float(insumo.cantidad_actual or 0):,.2f}",
                    _esc(unidad),
                    f"{float(insumo.stock_minimo or 0):,.2f}",
                    _money(insumo.costo_unitario),
                ]
            )
        return self._tabla(
            ["Insumo", "Existencia", "Unidad", "Mínimo", "Costo unitario"],
            filas,
        )

    def _bloque_anulaciones(self, datos: dict) -> str:
        anuladas = datos.get("anuladas") or {}
        devoluciones = datos.get("devoluciones") or {}
        return self._kpis(
            [
                ("Órdenes anuladas", _entero(anuladas.get("ordenes")), PALETA["rojo"]),
                ("Monto anulado", _money(anuladas.get("monto")), PALETA["rojo"]),
                ("Unidades devueltas", _entero(devoluciones.get("unidades")), PALETA["amarillo"]),
                ("Monto devuelto", _money(devoluciones.get("monto")), PALETA["amarillo"]),
            ]
        )

    def _bloque_nomina(self, datos: dict) -> str:
        return self._kpis(
            [
                ("Pagos realizados", _entero(datos.get("pagos")), PALETA["azul"]),
                ("Monto pagado", _money(datos.get("monto")), PALETA["rojo"]),
            ]
        )

    def _bloque_auditoria(self, datos: list[RegistroAuditoria]) -> str:
        return self._tabla(
            ["Fecha", "Acción", "Descripción", "Usuario"],
            [
                [
                    _fecha(registro.ocurrido_en),
                    _esc(registro.accion),
                    _esc(registro.descripcion),
                    _esc(registro.actor_username),
                ]
                for registro in datos
            ],
        )

    def _bloque_estudio(self, datos: dict) -> str:
        def lista(titulo: str, valores: list, color: str) -> str:
            if not valores:
                return ""
            items = "".join(
                f'<li style="margin:4px 0;font-size:13px;color:{PALETA["texto"]};">{_esc(v)}</li>'
                for v in valores
            )
            return (
                f'<p style="margin:12px 0 4px;font-size:12px;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:1px;color:{color};">{_esc(titulo)}</p>'
                f'<ul style="margin:0;padding-left:18px;">{items}</ul>'
            )

        resumen = datos.get("resumen") or ""
        return (
            f'<p style="font-size:14px;line-height:1.55;color:{PALETA["texto"]};margin:0;">'
            f"{_esc(resumen)}</p>"
            + lista("Fortalezas", datos.get("fortalezas") or [], PALETA["turquesa"])
            + lista("Oportunidades de mejora", datos.get("debilidades") or [], PALETA["rojo"])
            + lista("Estrategias recomendadas", datos.get("estrategias") or [], PALETA["azul"])
        )

    def render_html(
        self,
        tipo: str,
        secciones: list[str],
        datos: dict[str, Any],
        desde: date,
        hasta: date,
        asunto: str,
    ) -> str:
        bloques = []
        for indice, clave in enumerate(
            [seccion["clave"] for seccion in SECCIONES if seccion["clave"] in secciones]
        ):
            contenido = datos.get(clave)
            if contenido is None:
                continue
            render = getattr(self, f"_bloque_{clave}", None)
            if render is None:
                continue
            datos_bloque = contenido
            cuerpo = render(datos_bloque)
            nombre = SECCIONES_POR_CLAVE[clave]["nombre"]
            if es_sensible(clave):
                nombre += " · información sensible"
            bloques.append(self._bloque(nombre, cuerpo, primero=indice == 0))

        if not bloques:
            bloques.append(
                f'<p style="font-size:13px;color:{PALETA["suave"]};">'
                "Este correo no incluye secciones activas.</p>"
            )

        tipo_nombre = TIPOS_POR_CLAVE.get(tipo, {}).get("nombre", tipo)
        rango = f"{_fecha(desde)} al {_fecha(hasta)}"
        return (
            f'<div style="margin:0;padding:24px;background:{PALETA["fondo"]};'
            f'font-family:Inter,Arial,Helvetica,sans-serif;">'
            f'<div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:16px;'
            f'overflow:hidden;border:1px solid {PALETA["borde"]};">'
            f'<div style="background:{PALETA["azul"]};padding:24px;">'
            f'<div style="font-size:11px;font-weight:700;letter-spacing:2px;'
            f'text-transform:uppercase;color:{PALETA["amarillo"]};">Sazón Caribeño</div>'
            f'<h1 style="margin:6px 0 0;font-size:22px;line-height:1.25;color:#ffffff;">'
            f"{_esc(asunto)}</h1>"
            f'<p style="margin:8px 0 0;font-size:12px;color:#cfe3f5;">'
            f"{_esc(tipo_nombre)} · {_esc(rango)}</p></div>"
            f'<div style="padding:24px;">{"".join(bloques)}</div>'
            f'<div style="padding:16px 24px;background:#f1f5f9;color:{PALETA["suave"]};'
            f'font-size:11px;line-height:1.5;">Correo generado por el sistema de '
            f"Sazón Caribeño. Si recibiste este mensaje por error, ignóralo.</div>"
            f"</div></div>"
        )

    # ------------------------------------------------------------------ #
    #  Preparación y envío
    # ------------------------------------------------------------------ #
    def _destinatarios_para_envio(self, ids: Optional[list[int]]) -> list[str]:
        if ids is None:
            return []
        if not ids:
            return []
        destinatarios = list(
            self.db.execute(
                select(DestinatarioCorreo).where(
                    DestinatarioCorreo.id.in_(ids),
                    DestinatarioCorreo.activo.is_(True),
                )
            ).scalars()
        )
        return [destinatario.email for destinatario in destinatarios]

    def _resolver_envio(
        self,
        tipo: str,
        secciones: Optional[list[str]],
        destinatario_ids: Optional[list[int]],
        desde: Optional[date],
        hasta: Optional[date],
        asunto: Optional[str],
        referencia_id: Optional[int],
        usar_config: bool,
    ) -> dict[str, Any]:
        if tipo not in TIPOS_POR_CLAVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de correo desconocido: '{tipo}'.",
            )
        config = self._config(tipo)

        claves = secciones if secciones is not None else self._secciones_config(config)
        validas, invalidas = normalizar_secciones(tipo, claves)
        if invalidas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Secciones no disponibles para este correo: " + ", ".join(invalidas)
                ),
            )

        ids = destinatario_ids if destinatario_ids is not None else self._ids_config(config)
        emails = self._destinatarios_para_envio(ids)
        if not emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No hay destinatarios activos seleccionados. Agrega o marca al "
                    "menos un destinatario antes de enviar."
                ),
            )

        rango_desde, rango_hasta = self._rango(tipo, desde, hasta)
        datos = {
            clave: self._datos(clave, rango_desde, rango_hasta, referencia_id)
            for clave in validas
        }
        asunto_final = (asunto or "").strip() or self._asunto(tipo, rango_desde, rango_hasta)
        html = self.render_html(tipo, validas, datos, rango_desde, rango_hasta, asunto_final)
        return {
            "tipo": tipo,
            "asunto": asunto_final[:200],
            "secciones": validas,
            "emails": emails,
            "html": html,
            "desde": rango_desde,
            "hasta": rango_hasta,
        }

    def _asunto(self, tipo: str, desde: date, hasta: date) -> str:
        base = ASUNTO_POR_TIPO.get(tipo, "Informe de Sazón Caribeño")
        if tipo in {"manual", "resumen_semanal", "resumen_mensual"}:
            return f"{base} · {_fecha(desde)} al {_fecha(hasta)}"
        return base

    def preparar(
        self,
        tipo: str,
        secciones: Optional[list[str]] = None,
        destinatario_ids: Optional[list[int]] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        asunto: Optional[str] = None,
        actor_id: Optional[int] = None,
        referencia_id: Optional[int] = None,
    ) -> EnvioCorreo:
        resolucion = self._resolver_envio(
            tipo,
            secciones,
            destinatario_ids,
            desde,
            hasta,
            asunto,
            referencia_id,
            usar_config=True,
        )
        envio = EnvioCorreo(
            tipo=tipo,
            asunto=resolucion["asunto"],
            estado=EstadoEnvio.PENDIENTE.value,
            html=resolucion["html"],
            destinatarios=resolucion["emails"],
            referencia_id=referencia_id,
            desde=resolucion["desde"].isoformat(),
            hasta=resolucion["hasta"].isoformat(),
            actor_id=actor_id,
        )
        self.db.add(envio)
        self.db.commit()
        self.db.refresh(envio)
        return envio

    def _enviar_brevo(self, asunto: str, html: str, destinatarios: list[str]) -> None:
        if not self.habilitado():
            raise ErrorEnvioCorreo(
                "El envío de correos no está configurado (BREVO_API_KEY o "
                "CORREO_REMITENTE faltantes)."
            )
        payload = {
            "sender": {
                "name": self.settings.CORREO_REMITENTE_NOMBRE or "Sazón Caribeño",
                "email": self.settings.CORREO_REMITENTE,
            },
            "to": [{"email": email} for email in destinatarios],
            "subject": asunto,
            "htmlContent": html,
            "textContent": "Correo del sistema Sazón Caribeño. Abre la versión HTML.",
        }
        try:
            respuesta = httpx.post(
                BREVO_URL,
                json=payload,
                headers={
                    "api-key": self.settings.BREVO_API_KEY,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                timeout=self.settings.CORREO_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise ErrorEnvioCorreo(f"No se pudo conectar con Brevo: {exc}") from exc

        if respuesta.status_code >= 400:
            detalle = respuesta.text[:300]
            raise ErrorEnvioCorreo(
                f"Brevo rechazó el correo ({respuesta.status_code}): {detalle}"
            )

    def _procesar(self, envio: EnvioCorreo) -> EnvioCorreo:
        emails = list(envio.destinatarios or [])
        try:
            self._enviar_brevo(envio.asunto, envio.html or "", emails)
            envio.estado = EstadoEnvio.ENVIADO.value
            envio.enviado_en = ahora_local()
            envio.error = None
        except Exception as exc:
            envio.intentos = int(envio.intentos or 0) + 1
            envio.error = str(exc)[:1000]
            if envio.intentos >= max(1, self.settings.CORREO_MAX_INTENTOS):
                envio.estado = EstadoEnvio.ERROR.value
            else:
                envio.estado = EstadoEnvio.PENDIENTE.value
        self.db.commit()
        self.db.refresh(envio)
        return envio

    def enviar_ahora(
        self,
        tipo: str,
        secciones: Optional[list[str]] = None,
        destinatario_ids: Optional[list[int]] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
        asunto: Optional[str] = None,
        actor_id: Optional[int] = None,
        referencia_id: Optional[int] = None,
    ) -> EnvioCorreo:
        if not self.habilitado():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.estado()["mensaje"],
            )
        envio = self.preparar(
            tipo,
            secciones,
            destinatario_ids,
            desde,
            hasta,
            asunto,
            actor_id,
            referencia_id,
        )
        return self._procesar(envio)

    def enviar_prueba(self, email: str, actor_id: Optional[int] = None) -> EnvioCorreo:
        email = normalizar_email(email)
        if not email_valido(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escribe un correo de prueba válido.",
            )
        if not self.habilitado():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.estado()["mensaje"],
            )
        asunto = "Prueba de correos · Sazón Caribeño"
        html = (
            f'<div style="padding:24px;background:{PALETA["fondo"]};'
            f'font-family:Inter,Arial,sans-serif;">'
            f'<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:14px;'
            f'padding:24px;border:1px solid {PALETA["borde"]};">'
            f'<h1 style="margin:0 0 8px;font-size:20px;color:{PALETA["azul"]};">'
            "Correos configurados correctamente</h1>"
            f'<p style="font-size:14px;line-height:1.6;color:{PALETA["texto"]};">'
            "Este es un mensaje de prueba del sistema de Sazón Caribeño. Si lo "
            "recibiste, Brevo y el remitente están bien configurados.</p>"
            f'<p style="font-size:13px;color:{PALETA["suave"]};">'
            f"Remitente: {_esc(self.settings.CORREO_REMITENTE)}</p>"
            "</div></div>"
        )
        envio = EnvioCorreo(
            tipo="manual",
            asunto=asunto,
            estado=EstadoEnvio.PENDIENTE.value,
            html=html,
            destinatarios=[email],
            actor_id=actor_id,
        )
        self.db.add(envio)
        self.db.commit()
        self.db.refresh(envio)
        return self._procesar(envio)

    def encolar(
        self,
        tipo: str,
        referencia_id: Optional[int] = None,
        desde: Optional[date] = None,
        hasta: Optional[date] = None,
    ) -> Optional[EnvioCorreo]:
        """Encola un correo automático si el tipo está activo y hay destinatarios."""
        config = self._config(tipo)
        if not config.activo:
            return None
        try:
            return self.preparar(
                tipo,
                self._secciones_config(config),
                self._ids_config(config),
                desde,
                hasta,
                None,
                None,
                referencia_id,
            )
        except HTTPException:
            return None

    # ------------------------------------------------------------------ #
    #  Cola y programados
    # ------------------------------------------------------------------ #
    def procesar_pendientes(self, limite: int = 5) -> int:
        if not self.habilitado():
            return 0
        pendientes = list(
            self.db.execute(
                select(EnvioCorreo)
                .where(EnvioCorreo.estado == EstadoEnvio.PENDIENTE.value)
                .order_by(EnvioCorreo.id)
                .limit(limite)
            ).scalars()
        )
        for envio in pendientes:
            self._procesar(envio)
        return len(pendientes)

    def _clave_programado(self, tipo: str, ahora: datetime) -> str:
        if tipo == "resumen_semanal":
            iso = ahora.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        if tipo == "resumen_mensual":
            anterior = rango_mes_anterior(ahora.date())
            return anterior[0].strftime("%Y-%m")
        return ahora.date().isoformat()

    def _toca_ahora(self, tipo: str, ahora: datetime, hora: int) -> bool:
        if ahora.hour < hora:
            return False
        if tipo == "resumen_semanal":
            return ahora.weekday() == 0
        if tipo == "resumen_mensual":
            return ahora.day == 1
        return True

    def evaluar_programados(self) -> int:
        """Encola los correos programados que correspondan a este momento."""
        if not self.habilitado():
            return 0
        ahora = ahora_local()
        encolados = 0
        for tipo in TIPOS_PROGRAMADOS:
            config = self._config(tipo)
            if not config.activo:
                continue
            if not self._ids_config(config):
                continue
            if not self._toca_ahora(tipo, ahora, config.hora):
                continue
            clave = self._clave_programado(tipo, ahora)
            if config.ultima_clave == clave:
                continue
            envio = self.encolar(tipo)
            if envio is None:
                continue
            config.ultima_clave = clave
            self.db.commit()
            encolados += 1
        return encolados

    def historial(self, limite: int = 50) -> list[EnvioCorreo]:
        return list(
            self.db.execute(
                select(EnvioCorreo).order_by(EnvioCorreo.id.desc()).limit(limite)
            ).scalars()
        )


def encolar_evento_seguro(tipo: str, referencia_id: Optional[int] = None, **kwargs) -> None:
    """Encola un correo de evento sin romper el flujo que lo disparó."""
    if tipo not in TIPOS_EVENTO:
        return
    from app.core.database import SessionLocal

    try:
        with SessionLocal() as db:
            CorreoService(db).encolar(tipo, referencia_id=referencia_id, **kwargs)
    except Exception as exc:  # pragma: no cover - salvaguarda de producción
        print(f"[CORREOS] No se pudo encolar el correo '{tipo}': {exc}")
