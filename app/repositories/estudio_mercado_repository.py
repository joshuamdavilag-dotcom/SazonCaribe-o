"""Consultas de datos y persistencia del módulo de Estudio de Mercado."""

from datetime import date, datetime, time, timedelta
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calendario import EventoCalendario
from app.models.estudio_mercado import (
    DocumentoEstudio,
    EstadoEstudio,
    EstudioMercado,
    MensajeEstudio,
    PeriodoEstudio,
    TipoEstudio,
)
from app.models.gasto import Gasto
from app.models.menu import CategoriaMenu, MenuItem
from app.models.orden import DetalleOrden, EstadoOrden, Orden
from app.models.salon import Mesa, Zona


def rango_datetime(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Devuelve el rango [inicio, fin) que cubre las fechas dadas."""
    inicio = datetime.combine(desde, time.min)
    fin = datetime.combine(hasta + timedelta(days=1), time.min)
    return inicio, fin


class EstudioMercadoRepository:
    """Fuente única de los datos que consume el estudio de mercado."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Ventas
    # ------------------------------------------------------------------ #
    @staticmethod
    def _condiciones_ventas(inicio: datetime, fin: datetime) -> tuple:
        return (
            Orden.estado == EstadoOrden.PAGADA,
            Orden.anulada.is_(False),
            Orden.fecha_creacion >= inicio,
            Orden.fecha_creacion < fin,
        )

    def resumen_ventas(self, desde: date, hasta: date) -> dict:
        """Totales de ventas cobradas en el periodo."""
        inicio, fin = rango_datetime(desde, hasta)
        fila = self.db.execute(
            select(
                func.count(Orden.id),
                func.coalesce(func.sum(Orden.total), 0),
                func.coalesce(func.sum(Orden.subtotal), 0),
                func.coalesce(func.sum(Orden.descuento_total), 0),
            ).where(*self._condiciones_ventas(inicio, fin))
        ).one()
        ordenes = int(fila[0] or 0)
        ingresos = float(fila[1] or 0)
        return {
            "ordenes": ordenes,
            "ingresos": round(ingresos, 2),
            "subtotal": round(float(fila[2] or 0), 2),
            "descuentos": round(float(fila[3] or 0), 2),
            "ticket_promedio": round(ingresos / ordenes, 2) if ordenes else 0.0,
        }

    def ordenes_anuladas(self, desde: date, hasta: date) -> dict:
        """Órdenes anuladas en el periodo (dinero que se dejó de cobrar)."""
        inicio, fin = rango_datetime(desde, hasta)
        fila = self.db.execute(
            select(
                func.count(Orden.id),
                func.coalesce(func.sum(Orden.total), 0),
            ).where(
                Orden.anulada.is_(True),
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
            )
        ).one()
        return {
            "ordenes": int(fila[0] or 0),
            "monto": round(float(fila[1] or 0), 2),
        }

    def devoluciones(self, desde: date, hasta: date) -> dict:
        """Unidades e importe devueltos de líneas ya cobradas."""
        inicio, fin = rango_datetime(desde, hasta)
        fila = self.db.execute(
            select(
                func.coalesce(func.sum(DetalleOrden.cantidad_devuelta), 0),
                func.coalesce(
                    func.sum(DetalleOrden.cantidad_devuelta * DetalleOrden.precio_unitario),
                    0,
                ),
            )
            .select_from(DetalleOrden)
            .join(Orden, Orden.id == DetalleOrden.orden_id)
            .where(
                DetalleOrden.cantidad_devuelta > 0,
                Orden.fecha_creacion >= inicio,
                Orden.fecha_creacion < fin,
            )
        ).one()
        return {
            "unidades": int(fila[0] or 0),
            "monto": round(float(fila[1] or 0), 2),
        }

    def metodos_pago(self, desde: date, hasta: date) -> list[dict]:
        """Órdenes e ingresos agrupados por método de pago."""
        inicio, fin = rango_datetime(desde, hasta)
        filas = self.db.execute(
            select(
                Orden.metodo_pago,
                func.count(Orden.id),
                func.coalesce(func.sum(Orden.total), 0),
            )
            .where(*self._condiciones_ventas(inicio, fin))
            .group_by(Orden.metodo_pago)
        ).all()
        return [
            {
                "metodo": fila[0].value if hasattr(fila[0], "value") else str(fila[0]),
                "ordenes": int(fila[1] or 0),
                "monto": round(float(fila[2] or 0), 2),
            }
            for fila in filas
        ]

    def productos_vendidos(self, desde: date, hasta: date) -> list[dict]:
        """Unidades e ingresos por platillo en el periodo."""
        inicio, fin = rango_datetime(desde, hasta)
        unidades = func.coalesce(
            func.sum(DetalleOrden.cantidad - DetalleOrden.cantidad_devuelta), 0
        )
        importe = func.coalesce(
            func.sum(
                (DetalleOrden.cantidad - DetalleOrden.cantidad_devuelta)
                * DetalleOrden.precio_unitario
            ),
            0,
        )
        filas = self.db.execute(
            select(
                MenuItem.id,
                MenuItem.nombre,
                CategoriaMenu.nombre,
                unidades,
                importe,
            )
            .select_from(DetalleOrden)
            .join(Orden, Orden.id == DetalleOrden.orden_id)
            .join(MenuItem, MenuItem.id == DetalleOrden.producto_id)
            .outerjoin(CategoriaMenu, CategoriaMenu.id == MenuItem.categoria_id)
            .where(*self._condiciones_ventas(inicio, fin))
            .group_by(MenuItem.id, MenuItem.nombre, CategoriaMenu.nombre)
            .order_by(unidades.desc())
        ).all()
        return [
            {
                "producto_id": int(fila[0]),
                "producto": fila[1],
                "categoria": fila[2] or "Sin categoría",
                "unidades": int(fila[3] or 0),
                "ingresos": round(float(fila[4] or 0), 2),
            }
            for fila in filas
        ]

    def productos_sin_ventas(self, ids_vendidos: Sequence[int]) -> list[dict]:
        """Platillos activos que no registraron ninguna venta."""
        consulta = (
            select(MenuItem.id, MenuItem.nombre, CategoriaMenu.nombre)
            .outerjoin(CategoriaMenu, CategoriaMenu.id == MenuItem.categoria_id)
            .where(MenuItem.disponible.is_(True))
        )
        if ids_vendidos:
            consulta = consulta.where(MenuItem.id.notin_(list(ids_vendidos)))
        filas = self.db.execute(consulta.order_by(MenuItem.nombre)).all()
        return [
            {"producto_id": int(fila[0]), "producto": fila[1], "categoria": fila[2] or "Sin categoría"}
            for fila in filas
        ]

    def categorias_vendidas(self, desde: date, hasta: date) -> list[dict]:
        """Unidades e ingresos por categoría del menú."""
        inicio, fin = rango_datetime(desde, hasta)
        unidades = func.coalesce(
            func.sum(DetalleOrden.cantidad - DetalleOrden.cantidad_devuelta), 0
        )
        importe = func.coalesce(
            func.sum(
                (DetalleOrden.cantidad - DetalleOrden.cantidad_devuelta)
                * DetalleOrden.precio_unitario
            ),
            0,
        )
        filas = self.db.execute(
            select(
                func.coalesce(CategoriaMenu.nombre, "Sin categoría"),
                unidades,
                importe,
            )
            .select_from(DetalleOrden)
            .join(Orden, Orden.id == DetalleOrden.orden_id)
            .join(MenuItem, MenuItem.id == DetalleOrden.producto_id)
            .outerjoin(CategoriaMenu, CategoriaMenu.id == MenuItem.categoria_id)
            .where(*self._condiciones_ventas(inicio, fin))
            .group_by(CategoriaMenu.nombre)
            .order_by(importe.desc())
        ).all()
        return [
            {
                "categoria": fila[0],
                "unidades": int(fila[1] or 0),
                "ingresos": round(float(fila[2] or 0), 2),
            }
            for fila in filas
        ]

    def ventas_por_zona(self, desde: date, hasta: date) -> list[dict]:
        """Ingresos por zona del salón y por venta para llevar."""
        inicio, fin = rango_datetime(desde, hasta)
        condiciones = self._condiciones_ventas(inicio, fin)

        filas = self.db.execute(
            select(
                Zona.nombre,
                func.count(func.distinct(Orden.id)),
                func.coalesce(func.sum(Orden.total), 0),
            )
            .select_from(Orden)
            .join(Mesa, Mesa.id == Orden.mesa_id)
            .join(Zona, Zona.id == Mesa.zona_id)
            .where(*condiciones)
            .group_by(Zona.nombre)
            .order_by(func.coalesce(func.sum(Orden.total), 0).desc())
        ).all()

        zonas = [
            {
                "zona": fila[0],
                "ordenes": int(fila[1] or 0),
                "ingresos": round(float(fila[2] or 0), 2),
            }
            for fila in filas
        ]

        fila = self.db.execute(
            select(
                func.count(Orden.id),
                func.coalesce(func.sum(Orden.total), 0),
            ).where(*condiciones, Orden.mesa_id.is_(None))
        ).one()
        if int(fila[0] or 0):
            zonas.append(
                {
                    "zona": "Para llevar / venta directa",
                    "ordenes": int(fila[0] or 0),
                    "ingresos": round(float(fila[1] or 0), 2),
                }
            )
        return zonas

    def ordenes_para_temporal(self, desde: date, hasta: date) -> list[tuple]:
        """Fecha y total de cada orden cobrada (para tendencias por día/hora)."""
        inicio, fin = rango_datetime(desde, hasta)
        return list(
            self.db.execute(
                select(Orden.fecha_creacion, Orden.total).where(
                    *self._condiciones_ventas(inicio, fin)
                )
            ).all()
        )

    # ------------------------------------------------------------------ #
    #  Compras y gastos
    # ------------------------------------------------------------------ #
    def gastos_por_categoria(self, desde: date, hasta: date) -> list[dict]:
        """Compras y gastos del periodo agrupados por categoría."""
        inicio, fin = rango_datetime(desde, hasta)
        filas = self.db.execute(
            select(
                Gasto.categoria,
                func.count(Gasto.id),
                func.coalesce(func.sum(Gasto.monto), 0),
            )
            .where(
                Gasto.eliminado.is_(False),
                Gasto.fecha >= inicio,
                Gasto.fecha < fin,
            )
            .group_by(Gasto.categoria)
            .order_by(func.coalesce(func.sum(Gasto.monto), 0).desc())
        ).all()
        return [
            {
                "categoria": fila[0].value if hasattr(fila[0], "value") else str(fila[0]),
                "movimientos": int(fila[1] or 0),
                "monto": round(float(fila[2] or 0), 2),
            }
            for fila in filas
        ]

    def nomina_pagada(self, desde: date, hasta: date) -> dict:
        """Nómina efectivamente pagada en el periodo (costo de personal)."""
        from app.models.nomina import Nomina

        inicio, fin = rango_datetime(desde, hasta)
        try:
            fila = self.db.execute(
                select(
                    func.count(Nomina.id),
                    func.coalesce(func.sum(Nomina.pago_neto), 0),
                ).where(
                    Nomina.estado == "PAGADO",
                    Nomina.fecha_pago.isnot(None),
                    Nomina.fecha_pago >= inicio,
                    Nomina.fecha_pago < fin,
                )
            ).one()
        except Exception:
            return {"pagos": 0, "monto": 0.0}
        return {"pagos": int(fila[0] or 0), "monto": round(float(fila[1] or 0), 2)}

    def eventos_calendario(self, desde: date, hasta: date) -> list[dict]:
        """Eventos planificados que se solapan con el periodo (contexto de temporada)."""
        try:
            filas = self.db.execute(
                select(
                    EventoCalendario.titulo,
                    EventoCalendario.fecha_inicio,
                    EventoCalendario.fecha_fin,
                    EventoCalendario.estado,
                ).where(
                    EventoCalendario.fecha_inicio <= hasta,
                    func.coalesce(EventoCalendario.fecha_fin, EventoCalendario.fecha_inicio)
                    >= desde,
                )
            ).all()
        except Exception:
            return []
        return [
            {
                "titulo": fila[0],
                "desde": fila[1].isoformat() if fila[1] else None,
                "hasta": (fila[2] or fila[1]).isoformat() if fila[1] else None,
                "estado": fila[3].value if hasattr(fila[3], "value") else str(fila[3]),
            }
            for fila in filas
        ]

    # ------------------------------------------------------------------ #
    #  Persistencia de estudios
    # ------------------------------------------------------------------ #
    def crear_estudio(self, **datos) -> EstudioMercado:
        estudio = EstudioMercado(**datos)
        self.db.add(estudio)
        self.db.commit()
        self.db.refresh(estudio)
        return estudio

    def obtener_estudio(self, estudio_id: int) -> Optional[EstudioMercado]:
        return self.db.get(EstudioMercado, estudio_id)

    def listar_estudios(self, limite: int = 40) -> list[EstudioMercado]:
        return list(
            self.db.execute(
                select(EstudioMercado)
                .order_by(EstudioMercado.creado_en.desc())
                .limit(limite)
            ).scalars().all()
        )

    def estudio_automatico(self, desde: date, hasta: date) -> Optional[EstudioMercado]:
        """Estudio automático del mismo rango (evita duplicados mensuales)."""
        return self.db.execute(
            select(EstudioMercado)
            .where(
                EstudioMercado.tipo == TipoEstudio.AUTOMATICO,
                EstudioMercado.desde == desde,
                EstudioMercado.hasta == hasta,
            )
            .order_by(EstudioMercado.creado_en.desc())
        ).scalars().first()

    def guardar_estudio(self, estudio: EstudioMercado) -> EstudioMercado:
        self.db.add(estudio)
        self.db.commit()
        self.db.refresh(estudio)
        return estudio

    def eliminar_estudio(self, estudio: EstudioMercado) -> None:
        self.db.delete(estudio)
        self.db.commit()

    # ------------------------------------------------------------------ #
    #  Documentos
    # ------------------------------------------------------------------ #
    def crear_documento(self, **datos) -> DocumentoEstudio:
        documento = DocumentoEstudio(**datos)
        self.db.add(documento)
        self.db.commit()
        self.db.refresh(documento)
        return documento

    def obtener_documento(self, documento_id: int) -> Optional[DocumentoEstudio]:
        return self.db.get(DocumentoEstudio, documento_id)

    def listar_documentos(self, limite: int = 30) -> list[DocumentoEstudio]:
        return list(
            self.db.execute(
                select(DocumentoEstudio)
                .order_by(DocumentoEstudio.creado_en.desc())
                .limit(limite)
            ).scalars().all()
        )

    def eliminar_documento(self, documento: DocumentoEstudio) -> None:
        self.db.delete(documento)
        self.db.commit()

    # ------------------------------------------------------------------ #
    #  Mensajes del chat
    # ------------------------------------------------------------------ #
    def crear_mensaje(self, **datos) -> MensajeEstudio:
        mensaje = MensajeEstudio(**datos)
        self.db.add(mensaje)
        self.db.commit()
        self.db.refresh(mensaje)
        return mensaje

    def listar_mensajes(self, limite: int = 60) -> list[MensajeEstudio]:
        filas = list(
            self.db.execute(
                select(MensajeEstudio)
                .order_by(MensajeEstudio.creado_en.desc())
                .limit(limite)
            ).scalars().all()
        )
        return list(reversed(filas))

    def limpiar_mensajes(self) -> int:
        mensajes = list(self.db.execute(select(MensajeEstudio)).scalars().all())
        for mensaje in mensajes:
            self.db.delete(mensaje)
        self.db.commit()
        return len(mensajes)

    def ultimo_estudio_completado(
        self, periodo: PeriodoEstudio
    ) -> Optional[EstudioMercado]:
        return self.db.execute(
            select(EstudioMercado)
            .where(
                EstudioMercado.periodo == periodo,
                EstudioMercado.estado == EstadoEstudio.COMPLETADO,
            )
            .order_by(EstudioMercado.hasta.desc())
        ).scalars().first()
