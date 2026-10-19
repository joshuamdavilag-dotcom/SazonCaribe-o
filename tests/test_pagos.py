import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.orden import EstadoOrden, Orden
from app.models.pago import EstadoPago, PagoOnline
from app.services.pago_service import PagoService
from app.services.payment_gateway import (
    CheckoutSession,
    GatewayNotConfiguredError,
    VerifiedPaymentEvent,
    WebhookVerificationError,
    _GATEWAYS,
    register_payment_gateway,
)


class FakeGateway:
    name = "test-provider"

    def __init__(self) -> None:
        self.checkout_calls = 0
        self.event = VerifiedPaymentEvent(
            event_id="evt-1",
            payment_reference="",
            provider_payment_id="pay-1",
            status="paid",
            amount="25.00",
            currency="NIO",
        )

    def create_checkout(
        self,
        *,
        reference: str,
        idempotency_key: str,
        amount: str,
        currency: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        self.checkout_calls += 1
        return CheckoutSession(
            provider_payment_id="pay-1",
            checkout_url="https://checkout.example.test/pay-1",
        )

    def verify_webhook(self, *, payload: bytes, headers: dict[str, str]):
        return self.event


class PagoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.orden = Orden(
            mesero_id=1,
            estado=EstadoOrden.ENTREGADA,
            total=Decimal("25.00"),
            subtotal=Decimal("25.00"),
            descuento_total=Decimal("0.00"),
            fecha_creacion=datetime.now(),
        )
        self.db.add(self.orden)
        self.db.commit()
        self.gateway = FakeGateway()
        register_payment_gateway(self.gateway)
        settings = SimpleNamespace(
            PAYMENT_PROVIDER="test-provider",
            PAYMENT_CURRENCY="NIO",
            PAYMENT_SUCCESS_URL="https://pos.example.test/pago-ok",
            PAYMENT_CANCEL_URL="https://pos.example.test/pago-cancelado",
        )
        self.settings_patch = patch(
            "app.services.pago_service.get_settings", return_value=settings
        )
        self.settings_patch.start()

    def tearDown(self) -> None:
        self.settings_patch.stop()
        _GATEWAYS.pop("test-provider", None)
        self.db.close()
        self.engine.dispose()

    def test_checkout_uses_idempotency_key_and_returns_hosted_url(self) -> None:
        pago = PagoService(self.db).iniciar_checkout(
            self.orden.id, "checkout-key-0001"
        )

        self.assertEqual(pago.estado, EstadoPago.PENDIENTE)
        self.assertEqual(
            pago.checkout_url, "https://checkout.example.test/pay-1"
        )
        self.assertEqual(pago.orden_activa_id, self.orden.id)

    def test_repeated_idempotency_key_returns_same_checkout(self) -> None:
        service = PagoService(self.db)
        first = service.iniciar_checkout(self.orden.id, "checkout-key-0007")
        second = service.iniciar_checkout(self.orden.id, "checkout-key-0007")

        self.assertEqual(first.id, second.id)
        self.assertEqual(self.gateway.checkout_calls, 1)

    def test_second_active_checkout_for_order_is_rejected(self) -> None:
        service = PagoService(self.db)
        service.iniciar_checkout(self.orden.id, "checkout-key-0008")

        with self.assertRaises(HTTPException) as raised:
            service.iniciar_checkout(self.orden.id, "checkout-key-0009")

        self.assertEqual(raised.exception.status_code, 409)

    def test_verified_webhook_marks_order_paid_once(self) -> None:
        service = PagoService(self.db)
        pago = service.iniciar_checkout(self.orden.id, "checkout-key-0002")
        self.gateway.event = VerifiedPaymentEvent(
            event_id="evt-paid-1",
            payment_reference=pago.referencia,
            provider_payment_id="pay-1",
            status="paid",
            amount="25.00",
            currency="NIO",
        )

        result = service.procesar_webhook("test-provider", b"signed", {})

        self.db.refresh(pago)
        self.db.refresh(self.orden)
        self.assertEqual(result, {"status": "confirmado"})
        self.assertEqual(pago.estado, EstadoPago.CONFIRMADO)
        self.assertIsNone(pago.orden_activa_id)
        self.assertEqual(self.orden.estado, EstadoOrden.PAGADA)
        self.assertEqual(
            service.procesar_webhook("test-provider", b"signed", {}),
            {"status": "duplicate"},
        )

    def test_changed_order_total_requires_review(self) -> None:
        service = PagoService(self.db)
        pago = service.iniciar_checkout(self.orden.id, "checkout-key-0003")
        self.orden.total = Decimal("30.00")
        self.db.commit()
        self.gateway.event = VerifiedPaymentEvent(
            event_id="evt-paid-2",
            payment_reference=pago.referencia,
            provider_payment_id="pay-1",
            status="paid",
            amount="25.00",
            currency="NIO",
        )

        result = service.procesar_webhook("test-provider", b"signed", {})

        self.db.refresh(pago)
        self.db.refresh(self.orden)
        self.assertEqual(result, {"status": "revision"})
        self.assertEqual(pago.estado, EstadoPago.REVISION)
        self.assertEqual(pago.monto_confirmado, Decimal("25.00"))
        self.assertEqual(self.orden.estado, EstadoOrden.ENTREGADA)

    def test_disabled_provider_cannot_start_checkout(self) -> None:
        settings = SimpleNamespace(
            PAYMENT_PROVIDER="disabled",
            PAYMENT_CURRENCY="NIO",
            PAYMENT_SUCCESS_URL="",
            PAYMENT_CANCEL_URL="",
        )

        with patch("app.services.pago_service.get_settings", return_value=settings):
            with self.assertRaises(GatewayNotConfiguredError):
                PagoService(self.db).iniciar_checkout(
                    self.orden.id, "checkout-key-0004"
                )

    def test_mismatched_webhook_amount_requires_review(self) -> None:
        service = PagoService(self.db)
        pago = service.iniciar_checkout(self.orden.id, "checkout-key-0005")
        self.gateway.event = VerifiedPaymentEvent(
            event_id="evt-paid-3",
            payment_reference=pago.referencia,
            provider_payment_id="pay-1",
            status="paid",
            amount="24.00",
            currency="NIO",
        )

        result = service.procesar_webhook("test-provider", b"signed", {})

        self.db.refresh(pago)
        self.db.refresh(self.orden)
        self.assertEqual(result, {"status": "revision"})
        self.assertEqual(pago.estado, EstadoPago.REVISION)
        self.assertEqual(pago.monto_confirmado, Decimal("24.00"))
        self.assertEqual(self.orden.estado, EstadoOrden.ENTREGADA)

    def test_bad_webhook_signature_is_rejected(self) -> None:
        pago = PagoService(self.db).iniciar_checkout(
            self.orden.id, "checkout-key-0006"
        )

        class InvalidSignatureGateway(FakeGateway):
            def verify_webhook(
                self, *, payload: bytes, headers: dict[str, str]
            ) -> VerifiedPaymentEvent:
                raise WebhookVerificationError()

        _GATEWAYS["test-provider"] = InvalidSignatureGateway()
        with self.assertRaises(HTTPException) as raised:
            PagoService(self.db).procesar_webhook(
                "test-provider", b"bad", {}
            )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(self.db.get(PagoOnline, pago.id).estado, EstadoPago.PENDIENTE)


if __name__ == "__main__":
    unittest.main()
