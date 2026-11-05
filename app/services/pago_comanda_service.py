import base64
import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.models.orden import DetalleOrden, EstadoOrden, MetodoPago, Orden
from app.models.pago import EstadoPago, PagoOnline
from app.models.pago_comanda import DivisionPagoComanda, PagoComanda
from app.models.personal import Usuario
from app.services.salon_service import SalonService


CENTAVO = Decimal("0.01")


def _a_centavos(monto: Decimal) -> int:
    return int((monto.quantize(CENTAVO, rounding=ROUND_HALF_UP) * 100))


def _monto_centavos(centavos: int) -> Decimal:
    return (Decimal(centavos) / 100).quantize(CENTAVO)


class PagoComandaService:
    """Registra pagos parciales, divisiones por persona y saldos de órdenes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _folio_factura(orden_id: int, pago_id: int) -> str:
        payload = f"sazon-caribeno:factura-pago:v1:{orden_id}:{pago_id}".encode()
        firma = hmac.new(
            get_settings().SECRET_KEY.encode(),
            payload,
            hashlib.sha256,
        ).digest()[:12]
        folio = base64.b32encode(firma).decode("ascii").rstrip("=")
        return f"FC-{folio}"

    @staticmethod
    def _importe_linea(detalle: DetalleOrden) -> Decimal:
        cantidad_vigente = detalle.cantidad - (detalle.cantidad_devuelta or 0)
        if cantidad_vigente <= 0:
            return Decimal("0.00")
        bruto = Decimal(str(detalle.precio_unitario)) * cantidad_vigente
        descuento = Decimal(str(detalle.descuento_monto or 0))
        if detalle.cantidad_devuelta and detalle.cantidad:
            descuento *= Decimal(cantidad_vigente) / Decimal(detalle.cantidad)
        return max(bruto - descuento, Decimal("0.00")).quantize(CENTAVO)

    @staticmethod
    def _importe_unidades(
        detalle: DetalleOrden,
        inicio: int,
        cantidad: int,
    ) -> Decimal:
        total_centavos = _a_centavos(PagoComandaService._importe_linea(detalle))
        total_unidades = detalle.cantidad - (detalle.cantidad_devuelta or 0)
        if total_unidades <= 0 or cantidad <= 0:
            return Decimal("0.00")
        base, sobrantes = divmod(total_centavos, total_unidades)
        extras = max(0, min(inicio + cantidad, sobrantes) - min(inicio, sobrantes))
        return _monto_centavos(base * cantidad + extras)

    @staticmethod
    def _cantidad_parte(cantidad: int, personas: int, parte: int) -> int:
        base, sobrantes = divmod(cantidad, personas)
        return base + (1 if parte <= sobrantes else 0)

    @staticmethod
    def _inicio_parte(cantidad: int, personas: int, parte: int) -> int:
        base, sobrantes = divmod(cantidad, personas)
        return (parte - 1) * base + min(parte - 1, sobrantes)

    def _obtener_orden(self, orden_id: int, bloquear: bool = False) -> Orden:
        statement = (
            select(Orden)
            .options(selectinload(Orden.detalles).joinedload(DetalleOrden.producto))
            .where(Orden.id == orden_id)
        )
        if bloquear:
            statement = statement.with_for_update()
        orden = self.db.execute(statement).scalar_one_or_none()
        if not orden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}.",
            )
        return orden

    def _suma_pagos(self, orden_id: int) -> Decimal:
        suma = self.db.execute(
            select(func.coalesce(func.sum(PagoComanda.monto), 0)).where(
                PagoComanda.orden_id == orden_id
            )
        ).scalar_one()
        return Decimal(str(suma or 0)).quantize(CENTAVO)

    def _divisiones(self, orden: Orden) -> list[dict]:
        divisiones = self.db.execute(
            select(DivisionPagoComanda)
            .options(
                joinedload(DivisionPagoComanda.pagos),
                joinedload(DivisionPagoComanda.detalle_orden)
                .joinedload(DetalleOrden.producto),
            )
            .where(DivisionPagoComanda.orden_id == orden.id)
            .order_by(DivisionPagoComanda.id)
        ).unique().scalars().all()
        resultado = []
        for division in divisiones:
            pagos_por_parte = {p.parte for p in division.pagos}
            detalle = division.detalle_orden
            partes = []
            offset = 0
            for numero in range(1, division.personas + 1):
                cantidad = self._cantidad_parte(
                    division.cantidad, division.personas, numero
                )
                monto = self._importe_unidades(
                    detalle, division.inicio_cantidad + offset, cantidad
                )
                partes.append({
                    "numero": numero,
                    "cantidad": cantidad,
                    "monto": monto,
                    "pagada": numero in pagos_por_parte,
                })
                offset += cantidad
            resultado.append({
                "id": division.id,
                "detalle_id": division.detalle_orden_id,
                "producto_nombre": (
                    detalle.producto.nombre if detalle.producto else
                    f"Producto #{detalle.producto_id}"
                ),
                "cantidad": division.cantidad,
                "personas": division.personas,
                "partes": partes,
            })
        return resultado

    def estado_pagos(self, orden_id: int) -> dict:
        orden = self._obtener_orden(orden_id)
        pagos = self.db.execute(
            select(PagoComanda)
            .options(joinedload(PagoComanda.usuario))
            .where(PagoComanda.orden_id == orden.id)
            .order_by(PagoComanda.creado_en, PagoComanda.id)
        ).unique().scalars().all()
        pagado = self._suma_pagos(orden.id)
        if orden.estado == EstadoOrden.PAGADA and pagado == 0:
            pagado = Decimal(str(orden.total)).quantize(CENTAVO)
        saldo = max(Decimal(str(orden.total)).quantize(CENTAVO) - pagado, Decimal("0.00"))

        divisiones = self._divisiones(orden)
        cantidad_dividida: dict[int, int] = {}
        for division in divisiones:
            cantidad_dividida[division["detalle_id"]] = (
                cantidad_dividida.get(division["detalle_id"], 0) + division["cantidad"]
            )
        items = []
        for detalle in orden.detalles:
            vigente = detalle.cantidad - (detalle.cantidad_devuelta or 0)
            reservada = cantidad_dividida.get(detalle.id, 0)
            disponible = max(vigente - reservada, 0)
            if disponible <= 0:
                continue
            inicio = vigente - disponible
            items.append({
                "detalle_id": detalle.id,
                "producto_nombre": (
                    detalle.producto.nombre if detalle.producto else
                    f"Producto #{detalle.producto_id}"
                ),
                "cantidad_total": vigente,
                "cantidad_disponible": disponible,
                "monto_disponible": self._importe_unidades(detalle, inicio, disponible),
            })
        return {
            "orden_id": orden.id,
            "total": Decimal(str(orden.total)).quantize(CENTAVO),
            "pagado_total": pagado,
            "saldo_pendiente": saldo,
            "completada": orden.estado == EstadoOrden.PAGADA or saldo == 0,
            "pagos": [
                {
                    "id": pago.id,
                    "usuario_id": pago.usuario_id,
                    "cobrador": pago.usuario.username if pago.usuario else "Proveedor en línea",
                    "metodo_pago": pago.metodo_pago,
                    "monto": pago.monto,
                    "creado_en": pago.creado_en,
                    "division_id": pago.division_id,
                    "parte": pago.parte,
                    "cantidad": pago.cantidad,
                    "folio_factura": self._folio_factura(orden.id, pago.id)
                    if pago.monto > 0 else None,
                }
                for pago in pagos
            ],
            "items": items,
            "divisiones": divisiones,
        }

    def cotizar_division(
        self, orden_id: int, detalle_id: int, cantidad: int, personas: int
    ) -> dict:
        orden = self._obtener_orden(orden_id)
        if orden.estado in (EstadoOrden.PAGADA, EstadoOrden.CANCELADA):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La orden ya no acepta pagos.",
            )
        detalle = next((d for d in orden.detalles if d.id == detalle_id), None)
        if not detalle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El ítem no pertenece a esta orden.",
            )
        if cantidad <= 0 or personas <= 0 or personas > cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe alcanzar para asignar al menos una unidad por persona.",
            )
        divisiones_previas = self.db.execute(
            select(DivisionPagoComanda).where(
                DivisionPagoComanda.detalle_orden_id == detalle.id
            )
        ).scalars().all()
        inicio = sum(d.cantidad for d in divisiones_previas)
        vigente = detalle.cantidad - (detalle.cantidad_devuelta or 0)
        if cantidad > vigente - inicio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad supera las unidades disponibles para dividir.",
            )
        partes = []
        offset = 0
        for numero in range(1, personas + 1):
            cantidad_parte = self._cantidad_parte(cantidad, personas, numero)
            monto_parte = self._importe_unidades(
                detalle,
                inicio + offset,
                cantidad_parte,
            )
            partes.append({
                "numero": numero,
                "cantidad": cantidad_parte,
                "monto": monto_parte,
                "pagada": False,
            })
            offset += cantidad_parte
        return {
            "cantidad": cantidad,
            "personas": personas,
            "partes": partes,
        }

    def registrar_pago(
        self,
        orden_id: int,
        metodo_pago: MetodoPago,
        usuario: Usuario,
        monto: Decimal | None = None,
        detalle_id: int | None = None,
        cantidad: int | None = None,
        personas: int | None = None,
        parte: int | None = None,
        division_id: int | None = None,
    ) -> dict:
        try:
            with self.db.begin_nested():
                orden = self._obtener_orden(orden_id, bloquear=True)
                if orden.estado in (EstadoOrden.PAGADA, EstadoOrden.CANCELADA):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="La orden ya no acepta pagos.",
                    )

                checkout_activo = self.db.execute(
                    select(PagoOnline.id).where(
                        PagoOnline.orden_activa_id == orden_id,
                        PagoOnline.estado == EstadoPago.PENDIENTE,
                    )
                ).scalar_one_or_none()
                if checkout_activo:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Hay un pago en línea pendiente para esta orden.",
                    )

                saldo = Decimal(str(orden.total)).quantize(CENTAVO) - self._suma_pagos(
                    orden.id
                )
                if saldo <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="La orden ya está completamente pagada.",
                    )

                if division_id is not None:
                    division = self.db.execute(
                        select(DivisionPagoComanda).where(
                            DivisionPagoComanda.id == division_id,
                            DivisionPagoComanda.orden_id == orden.id,
                        )
                    ).scalar_one_or_none()
                    if not division:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="No se encontró la división del ítem.",
                        )
                elif detalle_id is not None:
                    detalle = next(
                        (d for d in orden.detalles if d.id == detalle_id), None
                    )
                    if not detalle:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="El ítem no pertenece a esta orden.",
                        )
                    if cantidad is None or personas is None or parte is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Indique cantidad, personas y la parte que se cobrará.",
                        )
                    if personas > cantidad or parte > personas:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cada persona debe recibir al menos una unidad y la parte debe existir.",
                        )
                    divisiones_previas = self.db.execute(
                        select(DivisionPagoComanda).where(
                            DivisionPagoComanda.detalle_orden_id == detalle.id
                        )
                    ).scalars().all()
                    inicio = sum(d.cantidad for d in divisiones_previas)
                    vigente = detalle.cantidad - (detalle.cantidad_devuelta or 0)
                    if cantidad > vigente - inicio:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La cantidad supera las unidades disponibles para dividir.",
                        )
                    division = DivisionPagoComanda(
                        orden_id=orden.id,
                        detalle_orden_id=detalle.id,
                        cantidad=cantidad,
                        personas=personas,
                        inicio_cantidad=inicio,
                        creada_por=usuario.id,
                    )
                    self.db.add(division)
                    self.db.flush()
                else:
                    division = None

                if division:
                    if parte is None or parte > division.personas:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La parte seleccionada no existe en esta división.",
                        )
                    ya_pagada = self.db.execute(
                        select(PagoComanda.id).where(
                            PagoComanda.division_id == division.id,
                            PagoComanda.parte == parte,
                        )
                    ).scalar_one_or_none()
                    if ya_pagada:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Esa parte del ítem ya fue pagada.",
                        )
                    detalle = next(
                        d for d in orden.detalles
                        if d.id == division.detalle_orden_id
                    )
                    cantidad_parte = self._cantidad_parte(
                        division.cantidad, division.personas, parte
                    )
                    inicio_parte = self._inicio_parte(
                        division.cantidad, division.personas, parte
                    )
                    monto_pago = self._importe_unidades(
                        detalle, division.inicio_cantidad + inicio_parte, cantidad_parte
                    )
                else:
                    if monto is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Indique el monto del pago.",
                        )
                    monto_pago = Decimal(str(monto)).quantize(CENTAVO)
                    cantidad_parte = None

                if monto_pago <= 0 or monto_pago > saldo:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El pago debe ser mayor que C$0.00 y no superar el saldo de C${saldo:.2f}.",
                    )

                self.db.add(PagoComanda(
                    orden_id=orden.id,
                    usuario_id=usuario.id,
                    metodo_pago=metodo_pago,
                    monto=monto_pago,
                    division_id=division.id if division else None,
                    parte=parte if division else None,
                    cantidad=cantidad_parte,
                ))
                self.db.flush()
                saldo_restante = saldo - monto_pago
                if saldo_restante == 0:
                    orden.estado = EstadoOrden.PAGADA
                    orden.metodo_pago = metodo_pago
                    if orden.mesa_id:
                        SalonService(self.db).liberar_mesa_si_sin_comandas(orden.mesa_id)
                else:
                    orden.metodo_pago = metodo_pago

            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este pago ya fue registrado o la orden cambió mientras se cobraba.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

        return self.estado_pagos(orden_id)
