from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local
from app.models.calendario import (
    EstadoEventoCalendario,
    EventoCalendario,
)
from app.models.inventario import Insumo, Proveedor
from app.models.menu import MenuItem
from app.repositories.calendario_repository import CalendarioRepository
from app.schemas.calendario import EventoCalendarioRequest


class CalendarioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CalendarioRepository(db)

    def obtener_calendario(self, desde: date, hasta: date) -> dict:
        eventos = self.repo.obtener_eventos(desde, hasta)
        asistencias = self.repo.obtener_asistencias(desde, hasta)
        return {
            "eventos": [
                {
                    "id": evento.id,
                    "tipo": evento.tipo,
                    "titulo": evento.titulo,
                    "descripcion": evento.descripcion,
                    "fecha_inicio": evento.fecha_inicio,
                    "fecha_fin": evento.fecha_fin,
                    "hora_inicio": evento.hora_inicio,
                    "hora_fin": evento.hora_fin,
                    "estado": evento.estado,
                    "menu_item_id": evento.menu_item_id,
                    "menu_item_nombre": menu_item_nombre,
                    "insumo_id": evento.insumo_id,
                    "insumo_nombre": insumo_nombre,
                    "insumo_unidad_medida": insumo_unidad_medida,
                    "proveedor_id": evento.proveedor_id,
                    "proveedor_nombre": proveedor_nombre,
                    "cantidad_esperada": evento.cantidad_esperada,
                    "creado_por_id": evento.creado_por_id,
                    "creado_en": evento.creado_en,
                    "actualizado_en": evento.actualizado_en,
                    "completado_en": evento.completado_en,
                }
                for evento, menu_item_nombre, insumo_nombre, proveedor_nombre, insumo_unidad_medida in eventos
            ],
            "asistencias": asistencias,
        }

    def crear_evento(self, datos: EventoCalendarioRequest, usuario_id: int) -> EventoCalendario:
        self._validar_referencias(datos)
        evento = EventoCalendario(
            **datos.model_dump(exclude={"estado"}),
            estado=datos.estado,
            creado_por_id=usuario_id,
            completado_en=ahora_local() if datos.estado == EstadoEventoCalendario.REALIZADO else None,
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        return evento

    def actualizar_evento(self, evento_id: int, datos: EventoCalendarioRequest) -> EventoCalendario:
        evento = self.db.get(EventoCalendario, evento_id)
        if not evento:
            raise HTTPException(status_code=404, detail="Evento de calendario no encontrado")
        self._validar_referencias(datos)
        for campo, valor in datos.model_dump(exclude={"estado"}).items():
            setattr(evento, campo, valor)
        evento.estado = datos.estado
        if datos.estado == EstadoEventoCalendario.REALIZADO:
            evento.completado_en = evento.completado_en or ahora_local()
        else:
            evento.completado_en = None
        self.db.commit()
        self.db.refresh(evento)
        return evento

    def eliminar_evento(self, evento_id: int) -> None:
        evento = self.db.get(EventoCalendario, evento_id)
        if not evento:
            raise HTTPException(status_code=404, detail="Evento de calendario no encontrado")
        self.db.delete(evento)
        self.db.commit()

    def _validar_referencias(self, datos: EventoCalendarioRequest) -> None:
        if (
            datos.menu_item_id is not None
            and self.db.get(MenuItem, datos.menu_item_id) is None
        ):
            raise HTTPException(status_code=404, detail="El platillo seleccionado no existe")
        if datos.insumo_id is not None and self.db.get(Insumo, datos.insumo_id) is None:
            raise HTTPException(status_code=404, detail="El insumo seleccionado no existe")
        if (
            datos.proveedor_id is not None
            and self.db.get(Proveedor, datos.proveedor_id) is None
        ):
            raise HTTPException(status_code=404, detail="El proveedor seleccionado no existe")
