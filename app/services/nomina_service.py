from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.repositories.empleado_repository import EmpleadoRepository
from app.repositories.asistencia_repository import AsistenciaRepository
from app.repositories.nomina_repository import NominaRepository
from app.schemas.nomina import NominaGenerarRequest, NominaResponse


class NominaService:
    """
    Servicio de lógica de negocio para el módulo de nómina.

    Coordina el cálculo quincenal de salarios, horas extras
    y la generación de registros de nómina.
    """

    DIAS_MENSUALES = Decimal("30")
    HORAS_DIARIAS = Decimal("8")

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

            salario_base_mensual = Decimal(
                str(empleado.salario_base)
            )

            salario_quincenal_teorico = (
                salario_base_mensual / self.DIAS_MENSUALES * self.DIAS_MENSUALES / 2
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            asistencias = self.asistencia_repo.get_asistencias_por_rango_fechas(
                empleado.id,
                periodo.fecha_inicio,
                periodo.fecha_fin
            )

            total_horas_extras = sum(
                Decimal(str(a.horas_extras)) for a in asistencias
            )

            valor_dia = (
                salario_base_mensual / self.DIAS_MENSUALES
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            valor_hora_ordinaria = (
                valor_dia / self.HORAS_DIARIAS
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            pago_horas_extras = (
                total_horas_extras * valor_hora_ordinaria
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            pago_neto = salario_quincenal_teorico + pago_horas_extras

            nomina_data = {
                "empleado_id": empleado.id,
                "fecha_inicio": periodo.fecha_inicio,
                "fecha_fin": periodo.fecha_fin,
                "salario_base_mensual": salario_base_mensual,
                "salario_quincenal_teorico": salario_quincenal_teorico,
                "total_horas_extras": total_horas_extras,
                "pago_horas_extras": pago_horas_extras,
                "pago_neto": pago_neto,
                "estado": "PENDIENTE"
            }

            nomina_creada = self.nomina_repo.create(nomina_data)
            nominas_generadas.append(
                NominaResponse.model_validate(nomina_creada)
            )

        return nominas_generadas

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

        Obtiene las asistencias finalizadas, calcula horas normales
        y extras (a tarifa normal 1.0x) y crea el registro de nómina.

        Args:
            empleado_id: ID del empleado.
            fecha_inicio: Fecha de inicio del período.
            fecha_fin: Fecha de fin del período.

        Returns:
            NominaResponse con la nómina creada.

        Raises:
            HTTPException 404: Si el empleado no existe.
            HTTPException 400: Si ya existe nómina para ese período.
            HTTPException 400: Si no hay asistencias finalizadas en el período.
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

        asistencias = self.asistencia_repo.get_finalizadas_por_rango(
            empleado_id, fecha_inicio, fecha_fin
        )

        if not asistencias:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No hay asistencias finalizadas para el empleado "
                    f"{empleado_id} en el período {fecha_inicio} al {fecha_fin}"
                )
            )

        salario_base_mensual = Decimal(str(empleado.salario_base))

        valor_hora_normal = (
            salario_base_mensual / self.DIAS_MENSUALES / self.HORAS_DIARIAS
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        valor_hora_extra = valor_hora_normal

        total_horas_normales = Decimal("0")
        total_horas_extras = Decimal("0")

        for a in asistencias:
            horas_extras = Decimal(str(a.horas_extras))
            total_horas_extras += horas_extras

            if a.hora_salida_real and a.hora_entrada_real:
                total_trabajadas = Decimal(
                    str(
                        (a.hora_salida_real - a.hora_entrada_real)
                        .total_seconds()
                        / 3600
                    )
                )
                horas_normales = total_trabajadas - horas_extras
                if horas_normales < 0:
                    horas_normales = Decimal("0")
                total_horas_normales += horas_normales

        total_horas_normales = total_horas_normales.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total_horas_extras = total_horas_extras.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        pago_horas_normales = (
            total_horas_normales * valor_hora_normal
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        pago_horas_extras = (
            total_horas_extras * valor_hora_extra
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        bruto = pago_horas_normales + pago_horas_extras

        pago_neto = bruto

        nomina_data = {
            "empleado_id": empleado_id,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "salario_base_mensual": salario_base_mensual,
            "salario_quincenal_teorico": bruto,
            "total_horas_extras": total_horas_extras,
            "pago_horas_extras": pago_horas_extras,
            "pago_neto": pago_neto,
            "estado": "PENDIENTE"
        }

        nomina_creada = self.nomina_repo.create(nomina_data)
        return NominaResponse.model_validate(nomina_creada)
