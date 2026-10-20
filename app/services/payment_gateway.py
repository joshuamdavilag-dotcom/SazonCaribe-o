from dataclasses import dataclass
from typing import Literal, Mapping, Protocol


@dataclass(frozen=True)
class CheckoutSession:
    """Sesión de checkout emitida por un proveedor de pagos."""

    provider_payment_id: str
    checkout_url: str


@dataclass(frozen=True)
class VerifiedPaymentEvent:
    """Evento de webhook ya verificado y normalizado por el proveedor."""

    event_id: str
    payment_reference: str
    provider_payment_id: str
    status: Literal["paid", "failed", "cancelled"]
    amount: str
    currency: str


class PaymentGateway(Protocol):
    """Contrato que debe cumplir cada adaptador de proveedor de pagos."""

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
    ) -> CheckoutSession:
        """Crea una sesión de checkout y devuelve su ID y URL de pago."""
        ...

    def verify_webhook(
        self, *, payload: bytes, headers: Mapping[str, str]
    ) -> VerifiedPaymentEvent:
        """Verifica la firma del webhook y devuelve el evento normalizado."""
        ...


class GatewayNotConfiguredError(RuntimeError):
    """Indica que no existe un adaptador registrado para el proveedor solicitado."""

    pass


class GatewayRequestError(RuntimeError):
    """Indica un fallo transitorio al comunicarse con el proveedor de pagos."""

    pass


class WebhookVerificationError(RuntimeError):
    """Indica que la firma del webhook no pudo verificarse."""

    pass


_GATEWAYS: dict[str, PaymentGateway] = {}


def register_payment_gateway(gateway: PaymentGateway) -> None:
    """Registra un adaptador implementado para un proveedor concreto."""
    provider_name = gateway.name.strip().lower()
    if not provider_name:
        raise ValueError("El nombre del proveedor de pagos no puede estar vacío.")
    _GATEWAYS[provider_name] = gateway


def get_payment_gateway(provider_name: str) -> PaymentGateway:
    """Devuelve el adaptador registrado para un proveedor.

    Raises:
        GatewayNotConfiguredError: Si no hay un adaptador para el proveedor.
    """
    gateway = _GATEWAYS.get(provider_name.strip().lower())
    if gateway is None:
        raise GatewayNotConfiguredError(
            f"No hay un adaptador de pagos registrado para '{provider_name}'."
        )
    return gateway


def get_registered_gateway(provider_name: str) -> PaymentGateway | None:
    """Devuelve el adaptador registrado para un proveedor o None si no existe."""
    return _GATEWAYS.get(provider_name.strip().lower())
