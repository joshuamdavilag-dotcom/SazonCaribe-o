from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.gasto import Gasto, CategoriaGasto
from app.repositories.empleado_repository import EmpleadoRepository
from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.nomina_repository import NominaRepository, AdelantoSalarioRepository
from app.schemas.nomina import (
    NominaGenerarRequest, NominaResponse,
    AdelantoSalarioCreate, AdelantoSalarioResponse,
)


class NominaService:
    """
    Servicio de lógica de negocio para el módulo de nómina.

    Coordina el cálculo quincenal de salarios, horas extras,
    adelantos de salario y la generación de registros de nómina.
    """

    HORAS_MENSUALES = Decimal("240")

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.empleado_repo = EmpleadoRepository(db)
        self.asistencia_repo = AsistenciaRepository(db)
        self.nomina_repo = NominaRepository(db)
        self.adelanto_repo = AdelantoSalarioRepository(db)

    def registrar_adelanto(
        self,
        data: AdelantoSalarioCreate,
        usuario_id: int,
    ) -> AdelantoSalarioResponse:
        empleado = self.empleado_repo.get_by_id(data.empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {data.empleado_id}"
            )

        gasto = Gasto(
            concepto=f"Adelanto de salario - {empleado.nombre} {empleado.apellido}",
            monto=data.monto,
            categoria=CategoriaGasto.OPERATIVO,
            registrado_por=usuario_id,
        )
        self.db.add(gasto)
        self.db.flush()

        adelanto = self.adelanto_repo.create({
            "empleado_id": data.empleado_id,
            "monto": data.monto,
            "observacion": data.observacion,
            "registrado_por_id": usuario_id,
            "gasto_id": gasto.id,
        })

        return AdelantoSalarioResponse.model_validate(adelanto)

    def listar_adelantos_empleado(
        self,
        empleado_id: int,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
    ) -> List[AdelantoSalarioResponse]:
        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )
        adelantos = self.adelanto_repo.get_by_empleado(
            empleado_id, fecha_inicio, fecha_fin
        )
        return [AdelantoSalarioResponse.model_validate(a) for a in adelantos]

    def _obtener_total_adelantos(self, empleado_id: int, fecha_inicio: date, fecha_fin: date) -> Decimal:
        return self.adelanto_repo.sum_por_empleado_y_periodo(
            empleado_id, fecha_inicio, fecha_fin
        )

    def generar_nomina_quincenal(
        self,
        periodo: NominaGenerarRequest
    ) -> List[NominaResponse]:
        """
        Genera la nómina quincenal para todos los empleados activos.

        Args:
            periodo: Período de fechas (fecha_inicio y fecha_fin).

        Returns:
            Lista de nóminas generadas.
        """
        empleados = self.empleado_repo.get_activos()
        nominas_generadas = []

        for empleado in empleados:
            if self.nomina_repo.exists_by_periodo_y_empleado(
                empleado.id,
                periodo.fecha_inicio,
                periodo.fecha_fin
            ):
                continue

            nomina_data = self._calcular_periodo(
                empleado,
                periodo.fecha_inicio,
                periodo.fecha_fin
            )
            nomina_data["estado"] = "PENDIENTE"

            nomina_creada = self.nomina_repo.create(nomina_data)
            nominas_generadas.append(
                NominaResponse.model_validate(nomina_creada)
            )

        return nominas_generadas

    def _calcular_periodo(
        self,
        empleado,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        """
        Calcula la nómina de un empleado para un período.

        Fórmula: Pago = (salario_base / 2) + (horas_extras × tarifa) − adelantos.
        El salario base es fijo (no se recalculan horas ordinarias) y las
        horas extras se pagan a tarifa normal 1.0x (salario_base / 240).
        """
        salario_base_mensual = Decimal(str(empleado.salario_base))

        salario_quincenal_teorico = (
            salario_base_mensual / Decimal("2")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        tarifa_hora = (
            salario_base_mensual / self.HORAS_MENSUALES
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        asistencias = self.asistencia_repo.get_finalizadas_por_rango(
            empleado.id,
            fecha_inicio,
            fecha_fin
        )

        total_horas_extras = sum(
            (Decimal(str(a.horas_extras)) for a in asistencias),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        pago_horas_extras = (
            total_horas_extras * tarifa_hora
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_adelantos = self._obtener_total_adelantos(
            empleado.id, fecha_inicio, fecha_fin
        )

        pago_neto = (
            salario_quincenal_teorico + pago_horas_extras - total_adelantos
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if pago_neto < 0:
            pago_neto = Decimal("0.00")

        return {
            "empleado_id": empleado.id,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "salario_base_mensual": salario_base_mensual,
            "salario_quincenal_teorico": salario_quincenal_teorico,
            "total_horas_extras": total_horas_extras,
            "pago_horas_extras": pago_horas_extras,
            "total_adelantos": total_adelantos,
            "pago_neto": pago_neto,
        }

    def obtener_nomina(self, nomina_id: int) -> NominaResponse:
        """
        Obtiene un registro de nómina por su ID.

        Args:
            nomina_id: ID del registro de nómina.

        Returns:
            NominaResponse con los datos de la nómina.

        Raises:
            HTTPException 404: Si la nómina no existe.
        """
        from fastapi import HTTPException, status

        nomina = self.nomina_repo.get_by_id(nomina_id)
        if not nomina:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la nómina con ID {nomina_id}"
            )
        return NominaResponse.model_validate(nomina)

    def nominas_pendientes(self) -> List[NominaResponse]:
        """
        Obtiene todas las nóminas pendientes de pago.

        Returns:
            Lista de nóminas con estado "PENDIENTE".
        """
        nominas = self.nomina_repo.get_pendientes()
        return [NominaResponse.model_validate(n) for n in nominas]

    def nominas_pagadas(self) -> List[NominaResponse]:
        """
        Obtiene todas las nóminas pagadas.

        Returns:
            Lista de nóminas con estado "PAGADO".
        """
        nominas = self.nomina_repo.get_pagadas()
        return [NominaResponse.model_validate(n) for n in nominas]

    def pagar_nomina(self, nomina_id: int) -> NominaResponse:
        """
        Marca una nómina como pagada y registra la fecha de pago.

        Args:
            nomina_id: ID del registro de nómina a pagar.

        Returns:
            NominaResponse con la nómina actualizada.

        Raises:
            HTTPException 404: Si la nómina no existe.
            HTTPException 400: Si la nómina ya fue pagada.
        """
        from datetime import datetime
        from fastapi import HTTPException, status

        nomina = self.nomina_repo.get_by_id(nomina_id)
        if not nomina:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la nómina con ID {nomina_id}"
            )

        if nomina.estado == "PAGADO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La nómina con ID {nomina_id} ya fue pagada"
            )

        nomina_pagada = self.nomina_repo.update(
            nomina_id,
            {
                "estado": "PAGADO",
                "fecha_pago": datetime.now()
            }
        )
        return NominaResponse.model_validate(nomina_pagada)

    def historial_empleado(self, empleado_id: int) -> List[NominaResponse]:
        """
        Obtiene el historial de nóminas de un empleado.

        Args:
            empleado_id: ID del empleado.

        Returns:
            Lista de nóminas ordenadas por fecha descendente.
        """
        nominas = self.nomina_repo.get_by_empleado(empleado_id)
        return [NominaResponse.model_validate(n) for n in nominas]

    def calcular_nomina_periodo(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date
    ) -> NominaResponse:
        """
        Calcula la nómina de un empleado para un período específico.

        Usa salario base fijo (salario_base / 2) más compensación por
        horas extras a tarifa normal (salario_base / 240). No depende
        de las horas ordinarias registradas.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del período.
            fecha_fin: Fecha de fin del período.

        Returns:
            NominaResponse con la nómina creada.

        Raises:
            HTTPException 404: Si el empleado no existe.
            HTTPException 400: Si ya existe nómina para ese período.
        """
        from fastapi import HTTPException, status

        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )

        if self.nomina_repo.exists_by_periodo_y_empleado(
            empleado_id, fecha_inicio, fecha_fin
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ya existe nómina registrada para el empleado "
                    f"{empleado_id} en el período {fecha_inicio} al {fecha_fin}"
                )
            )

        nomina_data = self._calcular_periodo(
            empleado,
            fecha_inicio,
            fecha_fin
        )
        nomina_data["estado"] = "PENDIENTE"

        nomina_creada = self.nomina_repo.create(nomina_data)
        return NominaResponse.model_validate(nomina_creada)
