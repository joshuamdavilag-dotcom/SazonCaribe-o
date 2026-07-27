from datetime import datetime, date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asistencia import Asistencia
from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.turno_repository import TurnoRepository


def _get_ip_cliente(request) -> str:
    if not request or not request.client:
        return ""
    if request.headers.get("cf-connecting-ip"):
        return request.headers["cf-connecting-ip"]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


def _ip_allowed(ip: str) -> bool:
    settings = get_settings()
    allowed = {addr.strip() for addr in settings.ALLOWED_IPS.split(",") if addr.strip()}
    return ip in allowed


def iniciar_turno(
    db: Session,
    usuario_id: int,
    empleado_id: int,
    turno_id: int,
    ip_cliente: str,
    rol: str,
) -> Asistencia:
    turno_repo = TurnoRepository(db)
    asistencia_repo = AsistenciaRepository(db)

    turno = turno_repo.get_by_id(turno_id)
    if not turno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el turno con ID {turno_id}",
        )

    if rol == "Vendedor" and not _ip_allowed(ip_cliente):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: IP no autorizada ({ip_cliente})",
        )

    ahora = datetime.now()
    datos = {
        "empleado_id": empleado_id,
        "turno_id": turno_id,
        "fecha": date.today(),
        "hora_entrada_real": ahora,
        "ip_origen": ip_cliente,
    }

    asistencia = asistencia_repo.create(datos)
    return asistencia


def finalizar_turno(db: Session, asistencia_id: int) -> Asistencia:
    asistencia_repo = AsistenciaRepository(db)
    turno_repo = TurnoRepository(db)

    asistencia = asistencia_repo.get_by_id(asistencia_id)
    if not asistencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la asistencia con ID {asistencia_id}",
        )

    if asistencia.hora_salida_real is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta asistencia ya tiene registrada una salida",
        )

    ahora = datetime.now()
    horas_reales = (ahora - asistencia.hora_entrada_real).total_seconds() / 3600

    turno = turno_repo.get_by_id(asistencia.turno_id)
    horas_extras = Decimal("0.00")
    if horas_reales > turno.horas_teoricas:
        horas_extras = Decimal(str(round(horas_reales - turno.horas_teoricas, 2)))

    datos = {
        "hora_salida_real": ahora,
        "horas_extras": horas_extras,
    }

    asistencia_repo.update(asistencia_id, datos)
    asistencia_repo.db.refresh(asistencia)
    return asistencia


def calcular_nomina_quincenal(
    salario_mensual: float,
    horas_extras_totales: float,
    salario_base: float,
) -> dict:
    pago_quincenal_base = salario_mensual / 2
    valor_hora_extra = (salario_mensual / 30 / 8) * horas_extras_totales
    pago_total_antes_iva = pago_quincenal_base + valor_hora_extra

    return {
        "salario_mensual": salario_mensual,
        "salario_base": salario_base,
        "horas_extras_totales": horas_extras_totales,
        "pago_quincenal_base": round(pago_quincenal_base, 2),
        "valor_hora_extra": round(valor_hora_extra, 2),
        "pago_total_antes_iva": round(pago_total_antes_iva, 2),
    }
