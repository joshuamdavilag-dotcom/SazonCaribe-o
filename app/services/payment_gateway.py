from dataclasses import dataclass
from typing import Literal, Mapping, Protocol


@dataclass(frozen=True)
class CheckoutSession:
    provider_payment_id: str
    checkout_url: str


@dataclass(frozen=True)
class VerifiedPaymentEvent:
    event_id: str
    payment_reference: str
    provider_payment_id: str
    status: Literal["paid", "failed", "cancelled"]
    amount: str
    currency: str


class PaymentGateway(Protocol):
    name: str

    def create_checkout(
        self,
        *,
        reference: str,
        idempotency_key: str,
        amount: str,
        currency: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession: ...

    def verify_webhook(
        self, *, payload: bytes, headers: Mapping[str, str]
    ) -> VerifiedPaymentEvent: ...


class GatewayNotConfiguredError(RuntimeError):
    pass


class GatewayRequestError(RuntimeError):
    pass


class WebhookVerificationError(RuntimeError):
    pass


_GATEWAYS: dict[str, PaymentGateway] = {}


def register_payment_gateway(gateway: PaymentGateway) -> None:
    """Registra un adaptador implementado para un proveedor concreto."""
    provider_name = gateway.name.strip().lower()
    if not provider_name:
        raise ValueError("El nombre del proveedor de pagos no puede estar vacío.")
    _GATEWAYS[provider_name] = gateway


def get_payment_gateway(provider_name: str) -> PaymentGateway:
    gateway = _GATEWAYS.get(provider_name.strip().lower())
    if gateway is None:
        raise GatewayNotConfiguredError(
            f"No hay un adaptador de pagos registrado para '{provider_name}'."
        )
    return gateway


def get_registered_gateway(provider_name: str) -> PaymentGateway | None:
    return _GATEWAYS.get(provider_name.strip().lower())
