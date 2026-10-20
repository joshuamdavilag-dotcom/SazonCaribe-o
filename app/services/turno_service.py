from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local
from app.models.asistencia import Asistencia
from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.turno_repository import TurnoRepository
from app.utils.calculations import calcular_horas_extras


def _get_ip_cliente(request) -> str:
    """Obtiene la IP del cliente priorizando CF-Connecting-IP y X-Forwarded-For."""
    if not request or not request.client:
        return ""
    if request.headers.get("cf-connecting-ip"):
        return request.headers["cf-connecting-ip"]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


def iniciar_turno(
    db: Session,
    usuario_id: int,
    empleado_id: int,
    turno_id: int,
    ip_cliente: str,
) -> Asistencia:
    """Inicia el turno de un empleado creando su registro de asistencia.

    Idempotente: si el empleado ya tiene una asistencia abierta la reutiliza, y
    si ya finalizó su turno en el día de negocio vigente (ventana 7:00 AM a
    7:00 AM) rechaza la solicitud.

    Args:
        db: Sesión de base de datos.
        usuario_id: ID del usuario que inicia el turno.
        empleado_id: ID del empleado.
        turno_id: ID del turno a iniciar.
        ip_cliente: IP de origen para auditoría.

    Returns:
        La asistencia creada o la abierta existente.

    Raises:
        HTTPException 404: Si el turno no existe.
        HTTPException 400: Si el empleado ya finalizó su turno hoy.
    """
    turno_repo = TurnoRepository(db)
    asistencia_repo = AsistenciaRepository(db)

    turno = turno_repo.get_by_id(turno_id)
    if not turno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el turno con ID {turno_id}",
        )

    abierta = asistencia_repo.get_abierta_por_empleado(empleado_id)
    if abierta:
        return abierta

    ahora = ahora_local()
    registrada_hoy = asistencia_repo.get_asistencia_del_dia_negocio(
        empleado_id,
        ahora,
    )
    if registrada_hoy is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya registraste y finalizaste tu turno hoy",
        )

    datos = {
        "empleado_id": empleado_id,
        "turno_id": turno_id,
        "fecha": ahora.date(),
        "hora_entrada_real": ahora,
        "ip_origen": ip_cliente,
    }

    asistencia = asistencia_repo.create(datos)
    return asistencia


def finalizar_turno(db: Session, asistencia_id: int) -> Asistencia:
    """Finaliza el turno fijando la hora de salida y calculando las horas extras.

    Idempotente: si la asistencia ya tiene salida registrada, la devuelve sin
    cambios.

    Args:
        db: Sesión de base de datos.
        asistencia_id: ID de la asistencia a finalizar.

    Returns:
        La asistencia con la salida registrada.

    Raises:
        HTTPException 404: Si la asistencia no existe.
    """
    asistencia_repo = AsistenciaRepository(db)
    turno_repo = TurnoRepository(db)

    asistencia = asistencia_repo.get_by_id(asistencia_id)
    if not asistencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la asistencia con ID {asistencia_id}",
        )

    if asistencia.hora_salida_real is not None:
        return asistencia

    ahora = ahora_local()
    entrada = asistencia.hora_entrada_real
    turno = turno_repo.get_by_id(asistencia.turno_id)
    horas_extras = (
        calcular_horas_extras(
            entrada,
            ahora,
            turno.hora_entrada,
            turno.hora_salida,
        )
        if turno
        else Decimal("0.00")
    )

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
    """Calcula la nómina quincenal usando el salario base del empleado.

    El salario base tiene prioridad sobre el salario mensual para evitar montar
    pagos con valores del puesto o del historial cuando el empleado tiene una
    tasa individual distinta.
    """
    base_mensual = Decimal(str(salario_base if salario_base else salario_mensual))
    pago_quincenal_base = (
        (base_mensual / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    tarifa_hora = base_mensual / Decimal("240")
    horas_extra = Decimal(str(horas_extras_totales))
    valor_hora_extra = (
        (horas_extra * tarifa_hora).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    pago_total_antes_iva = (
        (pago_quincenal_base + valor_hora_extra).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    return {
        "salario_mensual": float(base_mensual),
        "salario_base": float(base_mensual),
        "horas_extras_totales": horas_extras_totales,
        "pago_quincenal_base": float(pago_quincenal_base),
        "valor_hora_extra": float(valor_hora_extra),
        "pago_total_antes_iva": float(pago_total_antes_iva),
    }
