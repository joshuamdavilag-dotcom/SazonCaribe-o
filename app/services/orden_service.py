from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.orden import Orden, DetalleOrden, EstadoOrden
from app.models.inventario import MovimientoInventario
from app.models.salon import EstadoMesa
from app.repositories.orden_repository import OrdenRepository
from app.repositories.salon_repository import SalonRepository
from app.repositories.menu_repository import MenuRepository
from app.schemas.orden import OrdenCreate, DetalleOrdenCreate
from app.services.gasto_service import GastoService


class OrdenService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.orden_repo = OrdenRepository(db)
        self.salon_repo = SalonRepository(db)
        self.menu_repo = MenuRepository(db)
        self.gasto_service = GastoService(db)

    # ================================================================== #
    #  Stock: validación, descuento y reversión                           #
    # ================================================================== #

    def validar_stock_suficiente(
        self,
        detalles: list[DetalleOrdenCreate],
    ) -> None:
        """Valida que haya stock suficiente para todos los ingredientes.

        Recorre cada platillo, busca su receta y verifica que cada
        ingrediente tenga stock_actual >= cantidad_necesaria * porciones.
        Lanza HTTPException 400 con mensaje descriptivo si falta stock.
        """
        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(item.producto_id)
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El producto con ID {item.producto_id} no existe",
                )
            for receta in producto.ingredientes_receta:
                insumo = receta.insumo
                cantidad_total = (
                    Decimal(str(receta.cantidad_necesaria)) * item.cantidad
                )
                if Decimal(str(insumo.cantidad_actual)) < cantidad_total:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"No hay suficiente '{insumo.nombre}' en "
                            f"inventario (disponible: "
                            f"{insumo.cantidad_actual}, "
                            f"requerido: {cantidad_total})"
                        ),
                    )

    def descontar_stock(
        self,
        detalles: list[DetalleOrdenCreate],
        contexto: str,
    ) -> None:
        """Descuenta insumos del inventario para los detalles proporcionados.

        Para cada platillo, busca su receta y por cada ingrediente:
        - Resta cantidad_necesaria * porciones del stock_actual
        - Registra un MovimientoInventario de tipo SALIDA
        - Auto-genera un Gasto de categoría SUMINISTROS
        """
        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(item.producto_id)
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El producto con ID {item.producto_id} no existe",
                )
            for receta in producto.ingredientes_receta:
                insumo = receta.insumo
                cantidad_total = (
                    Decimal(str(receta.cantidad_necesaria)) * item.cantidad
                )
                insumo.cantidad_actual -= cantidad_total
                self.db.add(MovimientoInventario(
                    insumo_id=insumo.id,
                    tipo="SALIDA",
                    cantidad=cantidad_total,
                    motivo=contexto,
                    fecha=datetime.now(),
                ))
                costo = cantidad_total * Decimal(
                    str(insumo.costo_unitario)
                )
                if costo > 0:
                    self.gasto_service.registrar_gasto_automatico(
                        insumo_id=insumo.id,
                        concepto=(
                            f"Receta: {insumo.nombre} — {contexto}"
                        ),
                        monto=costo,
                    )

    def revertir_stock(self, orden: Orden) -> None:
        """Revierte el stock descontado para todos los ítems de una orden.

        Se invoca cuando la orden pasa a estado CANCELADA.
        Para cada DetalleOrden, busca la receta del platillo y por
        cada ingrediente suma de vuelta cantidad_necesaria * porciones
        al stock_actual, registrando un MovimientoInventario de tipo
        ENTRADA como auditoría.
        """
        for detalle in orden.detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(
                detalle.producto_id
            )
            if not producto:
                continue
            for receta in producto.ingredientes_receta:
                insumo = receta.insumo
                cantidad_revertir = (
                    Decimal(str(receta.cantidad_necesaria)) * detalle.cantidad
                )
                insumo.cantidad_actual += cantidad_revertir
                self.db.add(MovimientoInventario(
                    insumo_id=insumo.id,
                    tipo="ENTRADA",
                    cantidad=cantidad_revertir,
                    motivo=f"Reversión Orden #{orden.id} cancelada",
                    fecha=datetime.now(),
                ))

    # ================================================================== #
    #  DetalleOrden creation (shared helper)                               #
    # ================================================================== #

    def _procesar_detalles(
        self,
        detalles: list[DetalleOrdenCreate],
        contexto: str,
    ) -> tuple[list[DetalleOrden], Decimal]:
        """Valida stock, descuenta inventario y crea DetalleOrden en memoria.

        Retorna (detalles_creados, total_acumulado).
        """
        self.validar_stock_suficiente(detalles)
        self.descontar_stock(detalles, contexto)

        detalles_creados: list[DetalleOrden] = []
        total_acumulado = Decimal("0.00")

        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(
                item.producto_id
            )
            precio_unitario = Decimal(str(producto.precio))
            total_acumulado += precio_unitario * item.cantidad

            detalles_creados.append(DetalleOrden(
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=precio_unitario,
                notas=item.notas,
            ))

        return detalles_creados, total_acumulado

    # ================================================================== #
    #  One-active-order-per-mesa validation                               #
    # ================================================================== #

    def _validar_orden_activa_por_mesa(self, mesa_id: int) -> None:
        ordenes_activas = self.orden_repo.obtener_ordenes_filtradas(
            mesa_id=mesa_id,
        )
        activas = [
            o for o in ordenes_activas
            if o.estado in (
                EstadoOrden.PENDIENTE,
                EstadoOrden.PREPARANDO,
                EstadoOrden.ENTREGADA,
            )
        ]
        if activas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"La mesa {mesa_id} ya tiene una orden activa "
                    f"(Orden #{activas[0].id}). "
                    f"Use POST /ordenes/{activas[0].id}/items "
                    f"para agregar ítems."
                ),
            )

    # ================================================================== #
    #  Crear orden (POST /)                                               #
    # ================================================================== #

    def crear_orden(
        self,
        orden_in: OrdenCreate,
        mesero_id: int,
    ) -> Orden:
        mesa = self.salon_repo.obtener_mesa_por_id(orden_in.mesa_id)
        if not mesa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La mesa especificada no existe",
            )

        if mesa.estado != EstadoMesa.LIBRE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"La mesa {mesa.numero} no está disponible. "
                    f"Estado actual: {mesa.estado.value}"
                ),
            )

        self._validar_orden_activa_por_mesa(orden_in.mesa_id)

        try:
            with self.db.begin_nested():
                detalles_creados, total = self._procesar_detalles(
                    orden_in.detalles,
                    contexto=f"Descuento por Orden Mesa {orden_in.mesa_id}",
                )

                orden_db = Orden(
                    mesa_id=orden_in.mesa_id,
                    mesero_id=mesero_id,
                    total=total,
                    estado=EstadoOrden.PENDIENTE,
                    detalles=detalles_creados,
                )
                self.orden_repo.crear_orden(orden_db)
                mesa.estado = EstadoMesa.OCUPADA

            self.db.commit()
            self.db.refresh(orden_db)
            return orden_db

        except Exception:
            self.db.rollback()
            raise

    # ================================================================== #
    #  Agregar ítems a orden existente — POST /{id}/items                  #
    # ================================================================== #

    def _agregar_items_interno(
        self,
        orden_id: int,
        nuevos_detalles: list,
    ) -> Orden:
        orden = self.orden_repo.obtener_por_id(orden_id)
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )
        if orden.estado in (EstadoOrden.PAGADA, EstadoOrden.CANCELADA):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se pueden agregar ítems a una orden "
                    f"{orden.estado.value}"
                ),
            )

        try:
            with self.db.begin_nested():
                detalles_creados, subtotal_nuevos = self._procesar_detalles(
                    nuevos_detalles,
                    contexto=f"Agregado a Orden #{orden_id}",
                )
                orden.total += subtotal_nuevos

                for detalle in detalles_creados:
                    detalle.orden_id = orden_id
                    self.db.add(detalle)

                if orden.estado != EstadoOrden.PENDIENTE:
                    orden.estado = EstadoOrden.PENDIENTE

            self.db.commit()
            self.db.refresh(orden)
            return orden

        except Exception:
            self.db.rollback()
            raise

    def agregar_items_canonico(
        self,
        orden_id: int,
        nuevos_detalles: list,
    ) -> Orden:
        return self._agregar_items_interno(orden_id, nuevos_detalles)

    # ================================================================== #
    #  Pagar orden + liberar mesa — PUT /{id}/pagar                       #
    # ================================================================== #

    def pagar_orden(self, orden_id: int) -> Orden:
        orden = self.orden_repo.obtener_por_id(orden_id)
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )
        if orden.estado == EstadoOrden.PAGADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La orden ya fue pagada.",
            )
        if orden.estado == EstadoOrden.CANCELADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede pagar una orden cancelada.",
            )

        try:
            with self.db.begin_nested():
                orden.estado = EstadoOrden.PAGADA

                mesa = self.salon_repo.obtener_mesa_por_id(orden.mesa_id)
                if mesa:
                    mesa.estado = EstadoMesa.LIBRE

            self.db.commit()
            self.db.refresh(orden)
            return orden

        except Exception:
            self.db.rollback()
            raise

    # ================================================================== #
    #  Cambio de estado (con reversión automática al cancelar)            #
    # ================================================================== #

    TRANSICIONES_VALIDAS: dict[EstadoOrden, set[EstadoOrden]] = {
        EstadoOrden.PENDIENTE: {EstadoOrden.PREPARANDO, EstadoOrden.CANCELADA},
        EstadoOrden.PREPARANDO: {EstadoOrden.ENTREGADA, EstadoOrden.CANCELADA},
        EstadoOrden.ENTREGADA: {EstadoOrden.PAGADA, EstadoOrden.CANCELADA},
        EstadoOrden.PAGADA: set(),
        EstadoOrden.CANCELADA: set(),
    }

    def cambiar_estado(
        self,
        orden_id: int,
        nuevo_estado: EstadoOrden,
    ) -> Orden:
        orden = self.orden_repo.obtener_por_id(orden_id)
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )

        permitidos = self.TRANSICIONES_VALIDAS.get(orden.estado, set())
        if nuevo_estado not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se puede cambiar de '{orden.estado.value}' "
                    f"a '{nuevo_estado.value}'. "
                    f"Transiciones permitidas desde "
                    f"'{orden.estado.value}': "
                    f"{', '.join(e.value for e in permitidos) or '(ninguna)'}"
                ),
            )

        if nuevo_estado == EstadoOrden.CANCELADA:
            try:
                with self.db.begin_nested():
                    self.revertir_stock(orden)
                    orden.estado = EstadoOrden.CANCELADA
                self.db.commit()
                self.db.refresh(orden)
                return orden
            except Exception:
                self.db.rollback()
                raise

        return self.orden_repo.actualizar_estado(orden, nuevo_estado)

    # ================================================================== #
    #  Consultas                                                          #
    # ================================================================== #

    def obtener_ordenes(
        self,
        estado: Optional[EstadoOrden] = None,
        mesa_id: Optional[int] = None,
    ) -> List[Orden]:
        return self.orden_repo.obtener_ordenes_filtradas(estado, mesa_id)

    def obtener_orden(self, orden_id: int) -> Orden:
        orden = self.orden_repo.obtener_por_id(orden_id)
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )
        return orden
