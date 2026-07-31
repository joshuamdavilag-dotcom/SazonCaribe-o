from datetime import date, datetime
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
from app.schemas.orden import OrdenCreate, DetalleOrdenCreate, VentaRetroactivaCreate
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

    def _convertir_si_necesario(
        self,
        receta_unidad_id: int | None,
        insumo,
        cantidad: Decimal,
    ) -> Decimal:
        """Convierte la cantidad de receta a la unidad base del insumo.

        Prioridad:
        1. Si la unidad de la receta coincide con unidad_empaque del insumo → factor_empaque.
        2. Si no, cadena global de conversión entre unidades.
        """
        if receta_unidad_id is None or receta_unidad_id == insumo.unidad_medida_id:
            return cantidad
        if (insumo.unidad_empaque_id is not None
                and receta_unidad_id == insumo.unidad_empaque_id
                and insumo.factor_empaque):
            return Decimal(str(round(float(cantidad) * insumo.factor_empaque, 4)))
        from app.services.conversion_service import convertir_cantidad
        resultado = convertir_cantidad(
            self.db, float(cantidad), receta_unidad_id, insumo.unidad_medida_id
        )
        return Decimal(str(round(resultado, 4)))

    def validar_stock_suficiente(
        self,
        detalles: list[DetalleOrdenCreate],
    ) -> None:
        """Valida que haya stock suficiente para todos los ingredientes.

        Si la receta especifica una unidad diferente a la del insumo,
        convierte automáticamente antes de comparar.
        """
        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(item.producto_id)
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El producto con ID {item.producto_id} no existe",
                )
            for receta in producto.ingredientes_receta:
                if receta.descuento_por_lote:
                    continue
                insumo = receta.insumo
                cantidad_base = Decimal(str(receta.cantidad_necesaria)) * item.cantidad
                cantidad_convertida = self._convertir_si_necesario(
                    receta.unidad_medida_id, insumo, cantidad_base
                )
                if Decimal(str(insumo.cantidad_actual)) < cantidad_convertida:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"No hay suficiente '{insumo.nombre}' en "
                            f"inventario (disponible: "
                            f"{insumo.cantidad_actual}, "
                            f"requerido: {cantidad_convertida})"
                        ),
                    )

    def descontar_stock(
        self,
        detalles: list[DetalleOrdenCreate],
        contexto: str,
    ) -> None:
        """Descuenta insumos del inventario para los detalles proporcionados.

        Si la receta especifica una unidad diferente a la del insumo,
        convierte automáticamente antes de descontar.
        """
        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(item.producto_id)
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El producto con ID {item.producto_id} no existe",
                )
            for receta in producto.ingredientes_receta:
                if receta.descuento_por_lote:
                    continue
                insumo = receta.insumo
                cantidad_base = (
                    Decimal(str(receta.cantidad_necesaria)) * item.cantidad
                )
                cantidad_convertida = self._convertir_si_necesario(
                    receta.unidad_medida_id, insumo, cantidad_base
                )
                insumo.cantidad_actual -= cantidad_convertida
                self.db.add(MovimientoInventario(
                    insumo_id=insumo.id,
                    tipo="SALIDA",
                    cantidad=cantidad_convertida,
                    motivo=contexto,
                    fecha=datetime.now(),
                ))
                costo = cantidad_convertida * Decimal(
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

        Si la receta especifica una unidad diferente a la del insumo,
        convierte automáticamente al revertir.
        """
        for detalle in orden.detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(
                detalle.producto_id
            )
            if not producto:
                continue
            for receta in producto.ingredientes_receta:
                if receta.descuento_por_lote:
                    continue
                insumo = receta.insumo
                cantidad_base = (
                    Decimal(str(receta.cantidad_necesaria)) * detalle.cantidad
                )
                cantidad_convertida = self._convertir_si_necesario(
                    receta.unidad_medida_id, insumo, cantidad_base
                )
                insumo.cantidad_actual += cantidad_convertida
                self.db.add(MovimientoInventario(
                    insumo_id=insumo.id,
                    tipo="ENTRADA",
                    cantidad=cantidad_convertida,
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
    ) -> tuple[list[DetalleOrden], Decimal, Decimal]:
        """Valida stock, descuenta inventario y crea DetalleOrden en memoria.

        Aplica el descuento en C$ del ítem (si lo trae) validando que no
        exceda el total de la línea.

        Retorna (detalles_creados, subtotal_acumulado, descuento_acumulado).
        """
        self.validar_stock_suficiente(detalles)
        self.descontar_stock(detalles, contexto)

        detalles_creados: list[DetalleOrden] = []
        subtotal_acumulado = Decimal("0.00")
        descuento_acumulado = Decimal("0.00")

        for item in detalles:
            producto = self.menu_repo.obtener_menu_item_por_id(
                item.producto_id
            )
            precio_unitario = (
                Decimal(str(item.precio_unitario))
                if item.precio_unitario is not None
                else Decimal(str(producto.precio))
            )
            base_linea = precio_unitario * item.cantidad
            subtotal_acumulado += base_linea

            descuento_monto = item.descuento_monto
            if descuento_monto is not None:
                descuento_monto = Decimal(str(descuento_monto)).quantize(Decimal("0.01"))
                if descuento_monto > base_linea:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"El descuento de C${descuento_monto} excede el total "
                            f"del ítem '{producto.nombre}' (C${base_linea})."
                        ),
                    )
                if descuento_monto > 0:
                    descuento_acumulado += descuento_monto

            descuento_porcentaje = None
            if descuento_monto and base_linea > 0:
                descuento_porcentaje = (
                    descuento_monto / base_linea * Decimal("100")
                ).quantize(Decimal("0.01"))

            detalles_creados.append(DetalleOrden(
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=precio_unitario,
                notas=item.notas,
                descuento_monto=descuento_monto,
                descuento_porcentaje=descuento_porcentaje,
                motivo_descuento=item.motivo_descuento,
            ))

        return detalles_creados, subtotal_acumulado, descuento_acumulado

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
        if orden_in.mesa_id:
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
                detalles_creados, subtotal, descuento_total = self._procesar_detalles(
                    orden_in.detalles,
                    contexto=(
                        f"Descuento por Orden Mesa {orden_in.mesa_id}"
                        if orden_in.mesa_id
                        else "Descuento por Orden Para Llevar"
                    ),
                )

                orden_db = Orden(
                    mesa_id=orden_in.mesa_id,
                    mesero_id=mesero_id,
                    total=max(subtotal - descuento_total, Decimal("0.00")),
                    subtotal=subtotal,
                    descuento_total=descuento_total,
                    nombre_cliente=orden_in.nombre_cliente,
                    estado=EstadoOrden.PENDIENTE,
                    detalles=detalles_creados,
                )
                self.orden_repo.crear_orden(orden_db)
                if orden_in.mesa_id:
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
                detalles_creados, subtotal_nuevos, descuento_nuevos = self._procesar_detalles(
                    nuevos_detalles,
                    contexto=f"Agregado a Orden #{orden_id}",
                )
                orden.subtotal += subtotal_nuevos
                orden.descuento_total = (
                    (orden.descuento_total or Decimal("0.00")) + descuento_nuevos
                )
                orden.total = max(
                    orden.subtotal - (orden.descuento_total or Decimal("0.00")),
                    Decimal("0.00"),
                )

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

                if orden.mesa_id:
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
    #  Venta retroactiva — POST /retroactiva                               #
    # ================================================================== #

    # ================================================================== #
    #  Descuentos                                                         #
    # ================================================================== #

    def aplicar_descuento_item(
        self,
        orden_id: int,
        detalle_id: int,
        tipo: str,
        valor: float,
        motivo: Optional[str] = None,
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
                detail="No se puede aplicar descuento a una orden pagada o cancelada.",
            )

        detalle = next((d for d in orden.detalles if d.id == detalle_id), None)
        if not detalle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el detalle con ID {detalle_id} en la orden {orden_id}",
            )

        try:
            with self.db.begin_nested():
                base_line_total = Decimal(str(detalle.precio_unitario)) * detalle.cantidad

                if tipo == "porcentaje":
                    pct = Decimal(str(valor))
                    detalle.descuento_porcentaje = pct
                    desc_monto = (base_line_total * pct / Decimal("100")).quantize(Decimal("0.01"))
                    detalle.descuento_monto = desc_monto
                else:
                    desc_monto = Decimal(str(valor)).quantize(Decimal("0.01"))
                    detalle.descuento_monto = desc_monto
                    if base_line_total > 0:
                        pct = (desc_monto / base_line_total * Decimal("100")).quantize(Decimal("0.01"))
                    else:
                        pct = Decimal("0.00")
                    detalle.descuento_porcentaje = pct

                detalle.motivo_descuento = motivo

                self._recalcular_totales(orden)

            self.db.commit()
            self.db.refresh(orden)
            return orden

        except Exception:
            self.db.rollback()
            raise

    def aplicar_descuento_global(
        self,
        orden_id: int,
        tipo: str,
        valor: float,
        motivo: Optional[str] = None,
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
                detail="No se puede aplicar descuento a una orden pagada o cancelada.",
            )

        try:
            with self.db.begin_nested():
                current_subtotal = sum(
                    Decimal(str(d.precio_unitario)) * d.cantidad
                    for d in orden.detalles
                )

                if tipo == "porcentaje":
                    pct = Decimal(str(valor))
                    desc_total = (current_subtotal * pct / Decimal("100")).quantize(Decimal("0.01"))
                else:
                    desc_total = Decimal(str(valor)).quantize(Decimal("0.01"))

                pct_item = Decimal("0.00")
                if current_subtotal > 0:
                    pct_item = (desc_total / current_subtotal * Decimal("100")).quantize(Decimal("0.01"))

                remaining = desc_total
                for d in orden.detalles:
                    base_line = Decimal(str(d.precio_unitario)) * d.cantidad
                    if remaining > 0 and current_subtotal > 0:
                        item_desc = (base_line * pct_item / Decimal("100")).quantize(Decimal("0.01"))
                        if item_desc > remaining:
                            item_desc = remaining
                        d.descuento_monto = (d.descuento_monto or Decimal("0.00")) + item_desc
                        d.descuento_porcentaje = pct_item
                        if motivo:
                            d.motivo_descuento = (
                                f"{d.motivo_descuento}; " if d.motivo_descuento else ""
                            ) + f"Global: {motivo}"
                        remaining -= item_desc
                    else:
                        if not d.descuento_monto or d.descuento_monto == 0:
                            d.descuento_monto = Decimal("0.00")
                            d.descuento_porcentaje = Decimal("0.00")

                self._recalcular_totales(orden)

            self.db.commit()
            self.db.refresh(orden)
            return orden

        except Exception:
            self.db.rollback()
            raise

    def _recalcular_totales(self, orden: Orden) -> None:
        subtotal = Decimal("0.00")
        descuento_total = Decimal("0.00")

        for d in orden.detalles:
            base = Decimal(str(d.precio_unitario)) * d.cantidad
            subtotal += base
            descuento_total += d.descuento_monto or Decimal("0.00")

        orden.subtotal = subtotal
        orden.descuento_total = descuento_total
        orden.total = max(subtotal - descuento_total, Decimal("0.00"))

    def quitar_descuento_item(
        self,
        orden_id: int,
        detalle_id: int,
    ) -> Orden:
        orden = self.orden_repo.obtener_por_id(orden_id)
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )

        detalle = next((d for d in orden.detalles if d.id == detalle_id), None)
        if not detalle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el detalle con ID {detalle_id}",
            )

        try:
            with self.db.begin_nested():
                detalle.descuento_porcentaje = None
                detalle.descuento_monto = None
                detalle.motivo_descuento = None
                self._recalcular_totales(orden)

            self.db.commit()
            self.db.refresh(orden)
            return orden

        except Exception:
            self.db.rollback()
            raise

    def crear_venta_retroactiva(
        self,
        venta_in: VentaRetroactivaCreate,
        mesero_id: int,
    ) -> Orden:
        try:
            with self.db.begin_nested():
                detalles_creados: list[DetalleOrden] = []
                total = Decimal("0.00")

                for item in venta_in.detalles:
                    producto = self.menu_repo.obtener_menu_item_por_id(
                        item.producto_id
                    )
                    if not producto:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"El producto con ID {item.producto_id} no existe",
                        )
                    precio = (
                        Decimal(str(item.precio_unitario))
                        if item.precio_unitario is not None
                        else Decimal(str(producto.precio))
                    )
                    total += precio * item.cantidad
                    detalles_creados.append(DetalleOrden(
                        producto_id=item.producto_id,
                        cantidad=item.cantidad,
                        precio_unitario=precio,
                        notas=item.notas,
                    ))

                ts = datetime.combine(venta_in.fecha, datetime.now().time())
                orden_db = Orden(
                    mesa_id=venta_in.mesa_id,
                    mesero_id=mesero_id,
                    total=total,
                    subtotal=total,
                    descuento_total=Decimal("0.00"),
                    nombre_cliente=venta_in.nombre_cliente,
                    estado=EstadoOrden.PAGADA,
                    detalles=detalles_creados,
                    fecha_creacion=ts,
                )
                self.orden_repo.crear_orden(orden_db)

            self.db.commit()
            self.db.refresh(orden_db)
            return orden_db

        except Exception:
            self.db.rollback()
            raise

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
