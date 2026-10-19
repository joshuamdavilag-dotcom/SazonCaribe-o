from decimal import Decimal, InvalidOperation
import logging
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orden import EstadoOrden, Orden
from app.models.salon import EstadoMesa
from app.models.pago import EstadoPago, PagoOnline
from app.repositories.pago_repository import PagoRepository
from app.repositories.salon_repository import SalonRepository
from app.services.payment_gateway import (
    GatewayNotConfiguredError,
    GatewayRequestError,
    PaymentGateway,
    WebhookVerificationError,
    get_payment_gateway,
)

logger = logging.getLogger(__name__)


class PagoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.pagos = PagoRepository(db)
        self.salon = SalonRepository(db)

    @staticmethod
    def proveedor_configurado() -> str:
        return get_settings().PAYMENT_PROVIDER.strip().lower()

    @classmethod
    def obtener_gateway(cls) -> PaymentGateway:
        provider = cls.proveedor_configurado()
        if provider == "disabled":
            raise GatewayNotConfiguredError(
                "Los pagos en línea están desactivados; configure un proveedor."
            )
        return get_payment_gateway(provider)

    def iniciar_checkout(
        self, orden_id: int, idempotency_key: str
    ) -> PagoOnline:
        settings = get_settings()
        gateway = self.obtener_gateway()
        for return_url in (settings.PAYMENT_SUCCESS_URL, settings.PAYMENT_CANCEL_URL):
            if return_url:
                parsed_return_url = urlparse(return_url)
                if parsed_return_url.scheme != "https" or not parsed_return_url.netloc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Las URLs de retorno de pagos deben usar HTTPS.",
                    )
        orden = self.db.get(Orden, orden_id)
        if orden is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la orden con ID {orden_id}",
            )
        if orden.estado in (EstadoOrden.PAGADA, EstadoOrden.CANCELADA):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede iniciar el pago de una orden abierta.",
            )
        if orden.total <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La orden debe tener un total mayor que cero.",
            )

        existente = self.pagos.obtener_por_idempotencia(idempotency_key)
        if existente is not None:
            pago = existente
        else:
            if self.pagos.obtener_por_orden_activa(orden_id) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La orden ya tiene un checkout pendiente.",
                )
            pago = PagoOnline(
                orden_id=orden.id,
                orden_activa_id=orden.id,
                proveedor=gateway.name.strip().lower(),
                referencia=str(uuid4()),
                clave_idempotencia=idempotency_key,
                estado=EstadoPago.PENDIENTE,
                monto=orden.total,
                moneda=settings.PAYMENT_CURRENCY.upper(),
            )
            self.pagos.crear(pago)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                pago = self.pagos.obtener_por_idempotencia(idempotency_key)
                if pago is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="La orden ya tiene un checkout pendiente.",
                    )
            else:
                self.db.refresh(pago)

        if pago.orden_id != orden_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La clave de idempotencia ya se usó en otra orden.",
            )
        if pago.monto != orden.total:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El total de la orden cambió; use una clave nueva.",
            )
        if pago.proveedor != gateway.name.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La clave de idempotencia pertenece a otro proveedor.",
            )
        if pago.moneda != settings.PAYMENT_CURRENCY.upper():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La moneda configurada cambió; use una clave nueva.",
            )
        if pago.checkout_url or pago.estado != EstadoPago.PENDIENTE:
            return pago

        try:
            checkout = gateway.create_checkout(
                reference=pago.referencia,
                idempotency_key=idempotency_key,
                amount=f"{pago.monto:.2f}",
                currency=pago.moneda,
                success_url=settings.PAYMENT_SUCCESS_URL,
                cancel_url=settings.PAYMENT_CANCEL_URL,
            )
        except GatewayRequestError as exc:
            self.db.rollback()
            logger.error(
                "Fallo al iniciar checkout con proveedor %s: %s",
                pago.proveedor,
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "El proveedor no pudo iniciar el checkout. El intento quedó "
                    "pendiente; reintente con la misma clave de idempotencia."
                ),
            ) from exc

        checkout_url = checkout.checkout_url
        parsed_url = urlparse(checkout_url) if isinstance(checkout_url, str) else None
        if (
            not isinstance(checkout.provider_payment_id, str)
            or not checkout.provider_payment_id
            or len(checkout.provider_payment_id) > 150
            or parsed_url is None
            or parsed_url.scheme != "https"
            or not parsed_url.netloc
        ):
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="El proveedor devolvió una sesión de checkout inválida.",
            )

        pago.pago_proveedor_id = checkout.provider_payment_id
        pago.checkout_url = checkout.checkout_url
        self.db.commit()
        self.db.refresh(pago)
        return pago

    def consultar_pago(self, pago_id: int) -> PagoOnline:
        pago = self.db.get(PagoOnline, pago_id)
        if pago is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el pago con ID {pago_id}",
            )
        return pago

    def procesar_webhook(
        self, provider_name: str, payload: bytes, headers: dict[str, str]
    ) -> dict[str, str]:
        configured_provider = self.proveedor_configurado()
        if configured_provider == "disabled" or provider_name != configured_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Este proveedor no está habilitado para pagos.",
            )

        try:
            gateway = get_payment_gateway(provider_name)
        except GatewayNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

        try:
            event = gateway.verify_webhook(payload=payload, headers=headers)
        except WebhookVerificationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo verificar la firma del webhook.",
            ) from exc

        if (
            not isinstance(event.event_id, str)
            or not event.event_id
            or len(event.event_id) > 150
            or not isinstance(event.payment_reference, str)
            or not event.payment_reference
            or len(event.payment_reference) > 36
            or not isinstance(event.provider_payment_id, str)
            or not event.provider_payment_id
            or len(event.provider_payment_id) > 150
            or not isinstance(event.currency, str)
            or len(event.currency) != 3
            or not event.currency.isascii()
            or not event.currency.isalpha()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El webhook contiene datos incompletos o inválidos.",
            )

        if self.pagos.obtener_por_evento(provider_name, event.event_id):
            return {"status": "duplicate"}

        pago = self.pagos.obtener_por_referencia(
            event.payment_reference, bloquear=True
        )
        if pago is None or pago.proveedor != provider_name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró el intento de pago asociado al evento.",
            )
        if pago.estado in (
            EstadoPago.CONFIRMADO,
            EstadoPago.FALLIDO,
            EstadoPago.CANCELADO,
            EstadoPago.REVISION,
        ):
            return {"status": "already_processed"}

        try:
            monto_evento = Decimal(event.amount)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto recibido en el webhook no es válido.",
            ) from exc
        if not monto_evento.is_finite() or monto_evento < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto recibido en el webhook no es válido.",
            )

        orden = self.db.get(Orden, pago.orden_id)
        if orden is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la orden asociada al pago.",
            )

        pago.evento_proveedor_id = event.event_id
        pago.pago_proveedor_id = event.provider_payment_id
        if event.status == "paid":
            pago.monto_confirmado = monto_evento
            pago.moneda_confirmada = event.currency.upper()
            if (
                monto_evento != pago.monto
                or event.currency.upper() != pago.moneda
                or orden.total != pago.monto
                or orden.estado == EstadoOrden.CANCELADA
            ):
                pago.estado = EstadoPago.REVISION
            else:
                pago.estado = EstadoPago.CONFIRMADO
                orden.estado = EstadoOrden.PAGADA
                if orden.mesa_id:
                    mesa = self.salon.obtener_mesa_por_id(orden.mesa_id)
                    if mesa:
                        mesa.estado = EstadoMesa.LIBRE
                        mesa.apodo = None
        elif event.status == "failed":
            pago.estado = EstadoPago.FALLIDO
        elif event.status == "cancelled":
            pago.estado = EstadoPago.CANCELADO
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El proveedor reportó un estado de pago no soportado.",
            )
        pago.orden_activa_id = None

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if self.pagos.obtener_por_evento(provider_name, event.event_id):
                return {"status": "duplicate"}
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pudo registrar el evento de pago.",
            ) from exc
        return {"status": pago.estado.value.lower()}
