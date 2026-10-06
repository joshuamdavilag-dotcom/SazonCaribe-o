from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.pago import (
    CheckoutSessionResponse,
    DisponibilidadPagosResponse,
    PagoOnlineResponse,
)
from app.services.pago_service import PagoService
from app.services.payment_gateway import (
    GatewayNotConfiguredError,
    get_registered_gateway,
)

router = APIRouter()


def get_pago_service(db: Session = Depends(get_db)) -> PagoService:
    return PagoService(db)


@router.get(
    "/disponibilidad",
    response_model=DisponibilidadPagosResponse,
    summary="Consultar disponibilidad de pagos en línea",
    dependencies=[Depends(get_current_user)],
)
def disponibilidad_pagos() -> DisponibilidadPagosResponse:
    provider = PagoService.proveedor_configurado()
    configured = provider != "disabled"
    available = get_registered_gateway(provider) is not None if configured else False
    if available:
        message = "El adaptador del proveedor está registrado."
    elif configured:
        message = "El proveedor está configurado, pero su adaptador no está instalado."
    else:
        message = "Los pagos en línea están desactivados."
    return DisponibilidadPagosResponse(
        proveedor_configurado=provider,
        adaptador_disponible=available,
        habilitado=available,
        mensaje=message,
    )


@router.post(
    "/ordenes/{orden_id}/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar checkout para una orden",
    dependencies=[Depends(get_current_user)],
)
def iniciar_checkout(
    orden_id: int = Path(..., gt=0),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
        pattern="^[A-Za-z0-9._:-]+$",
    ),
    service: PagoService = Depends(get_pago_service),
) -> CheckoutSessionResponse:
    try:
        pago = service.iniciar_checkout(orden_id, idempotency_key)
    except GatewayNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return CheckoutSessionResponse(pago=PagoOnlineResponse.model_validate(pago))


@router.get(
    "/{pago_id}",
    response_model=PagoOnlineResponse,
    summary="Consultar un intento de pago",
    dependencies=[Depends(get_current_user)],
)
def consultar_pago(
    pago_id: int = Path(..., gt=0),
    service: PagoService = Depends(get_pago_service),
) -> PagoOnlineResponse:
    return PagoOnlineResponse.model_validate(service.consultar_pago(pago_id))


@router.post(
    "/webhooks/{provider_name}",
    summary="Recibir confirmación firmada del proveedor",
)
async def webhook_pago(
    provider_name: str,
    request: Request,
    service: PagoService = Depends(get_pago_service),
) -> dict[str, str]:
    payload = await request.body()
    return service.procesar_webhook(
        provider_name.strip().lower(), payload, dict(request.headers)
    )
