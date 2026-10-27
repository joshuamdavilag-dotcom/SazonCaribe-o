from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.tiempo import ahora_local, hoy_local
from app.repositories.caja_repository import CajaRepository
from app.repositories.orden_repository import OrdenRepository
from app.schemas.caja import (
    CierreAutomaticoResponse,
    CierreCajaResponse,
    HistorialDiarioResponse,
    VentasDiaResponse,
)
from app.schemas.orden import OrdenResponse
from app.services.auditoria_service import AuditoriaService
from app.services.configuracion_service import ConfiguracionService


class CajaService:
    """Reglas de negocio de la sesión de caja: consultas y cierre (archivado)."""

    CLAVE_ACTIVO = "caja_cierre_automatico_activo"
    CLAVE_ULTIMA_EJECUCION = "caja_cierre_automatico_ultima_ejecucion"
    CLAVE_ULTIMA_FECHA = "caja_cierre_automatico_ultima_fecha"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.caja_repo = CajaRepository(db)
        self.orden_repo = OrdenRepository(db)
        self.config = ConfiguracionService(db)

    def historial_diario(self) -> HistorialDiarioResponse:
        """Devuelve las órdenes pagadas de la caja abierta actual con sus totales."""
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()
        totales = self.caja_repo.calcular_totales(ordenes)

        return HistorialDiarioResponse(
            fecha=date.today().isoformat(),
            total_ventas=totales["total_ventas"],
            total_ordenes=totales["total_ordenes"],
            ordenes=[
                OrdenResponse.model_validate(o) for o in ordenes
            ],
        )

    def ventas_dia(self, es_gestor: bool) -> VentasDiaResponse:
        """Resumen de ventas del día para cualquier rol (sin datos financieros internos).

        Args:
            es_gestor: True si el solicitante es Administrador o Gerente; se refleja
                en la respuesta para que el frontend sepa si puede ver el panel completo.
        """
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()
        totales = self.caja_repo.calcular_totales(ordenes)

        return VentasDiaResponse(
            fecha=date.today().isoformat(),
            total_ventas=totales["total_ventas"],
            total_ordenes=totales["total_ordenes"],
            total_descuentos=totales["total_descuentos"],
            es_gestor=es_gestor,
            ordenes=[
                OrdenResponse.model_validate(o) for o in ordenes
            ],
        )

    def cerrar_caja(
        self,
        usuario_id: int,
    ) -> CierreCajaResponse:
        """Archiva la caja abierta: crea el cierre y lo vincula a órdenes y gastos.

        Raises:
            HTTPException 400: si no hay órdenes pagadas sin archivar.
        """
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()

        if not ordenes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay órdenes pagadas sin archivar.",
            )

        totales = self.caja_repo.calcular_totales(ordenes)
        gastos = self.caja_repo.obtener_gastos_sin_archivar()

        try:
            with self.db.begin_nested():
                cierre = self.caja_repo.crear_cierre(
                    total_ventas=totales["total_ventas"],
                    total_ordenes=totales["total_ordenes"],
                    cerrado_por=usuario_id,
                )
                if cierre.id is None:
                    raise ValueError("El cierre de caja no obtuvo un id tras el flush.")
                self.caja_repo.archivar_ordenes(ordenes, cierre)
                self.caja_repo.archivar_gastos(gastos, cierre)

            self.db.commit()
            self.db.refresh(cierre)
            return CierreCajaResponse.model_validate(cierre)

        except Exception as exc:
            self.db.rollback()
            print(f"[X] Error en cerrar_caja: {exc}")
            raise

    def estado_cierre_automatico(self) -> CierreAutomaticoResponse:
        """Devuelve si el cierre automático está activo y cuándo corre de nuevo."""
        activo = self.config.obtener_booleano(self.CLAVE_ACTIVO, False)
        ultima_fecha = self.config.obtener(self.CLAVE_ULTIMA_FECHA, "") or None
        hoy = hoy_local()

        proxima = None
        if activo:
            if ultima_fecha != hoy.isoformat():
                proxima = ahora_local()
            else:
                proxima = datetime.combine(hoy + timedelta(days=1), time.min)

        return CierreAutomaticoResponse(
            activo=activo,
            ultima_ejecucion=self.config.obtener_fecha(self.CLAVE_ULTIMA_EJECUCION),
            proxima_ejecucion=proxima,
            ultima_fecha=ultima_fecha,
        )

    def configurar_cierre_automatico(
        self,
        activo: bool,
        usuario_id: int | None = None,
        actor_username: str | None = None,
        actor_rol: str | None = None,
    ) -> CierreAutomaticoResponse:
        """Activa o desactiva el cierre automático y lo deja auditado.

        Al activarlo se registra el día actual como último día procesado para
        que el primer cierre automático ocurra en la próxima medianoche y no
        archive la caja abierta en el mismo instante de habilitarlo.
        """
        anterior = self.config.obtener_booleano(self.CLAVE_ACTIVO, False)
        self.config.guardar_booleano(self.CLAVE_ACTIVO, activo)
        if activo and not anterior:
            self.config.guardar(self.CLAVE_ULTIMA_FECHA, hoy_local().isoformat())

        if usuario_id is not None and actor_username:
            AuditoriaService.registrar(
                self.db,
                actor=self._actor(usuario_id, actor_username, actor_rol or ""),
                accion="CIERRE_AUTOMATICO_CONFIGURADO",
                entidad_tipo="CierreCaja",
                entidad_id=None,
                descripcion=(
                    "Cierre automático de caja "
                    + ("habilitado" if activo else "deshabilitado")
                    + " (medianoche hora Managua)"
                ),
                antes={"activo": anterior},
                despues={"activo": activo},
            )
        else:
            AuditoriaService.registrar_sistema(
                self.db,
                accion="CIERRE_AUTOMATICO_CONFIGURADO",
                entidad_tipo="CierreCaja",
                entidad_id=None,
                descripcion=(
                    "Cierre automático de caja "
                    + ("habilitado" if activo else "deshabilitado")
                    + " (medianoche hora Managua)"
                ),
                antes={"activo": anterior},
                despues={"activo": activo},
            )

        self.db.commit()
        return self.estado_cierre_automatico()

    def cerrar_caja_automatica(self) -> CierreCajaResponse | None:
        """Cierra la caja abierta sin intervención humana (medianoche).

        A diferencia del cierre manual, archiva también los gastos cuando no
        hay órdenes pagadas, porque su acumulación es justamente la causa de
        los errores de fecha y de cálculo de gastos. Si la caja está
        completamente vacía no crea un cierre y devuelve ``None``.
        """
        ordenes = self.caja_repo.obtener_ordenes_pagadas_sin_archivar()
        gastos = self.caja_repo.obtener_gastos_sin_archivar()

        if not ordenes and not gastos:
            return None

        totales = self.caja_repo.calcular_totales(ordenes)
        fecha_cierre = ahora_local()

        try:
            with self.db.begin_nested():
                cierre = self.caja_repo.crear_cierre(
                    total_ventas=totales["total_ventas"],
                    total_ordenes=totales["total_ordenes"],
                    cerrado_por=None,
                    fecha_cierre=fecha_cierre,
                )
                if cierre.id is None:
                    raise ValueError("El cierre de caja no obtuvo un id tras el flush.")
                self.caja_repo.archivar_ordenes(ordenes, cierre)
                self.caja_repo.archivar_gastos(gastos, cierre)

                AuditoriaService.registrar_sistema(
                    self.db,
                    accion="CIERRE_CAJA_AUTOMATICO",
                    entidad_tipo="CierreCaja",
                    entidad_id=cierre.id,
                    descripcion=(
                        "Cierre de caja automático de medianoche: "
                        f"{totales['total_ordenes']} orden(es), "
                        f"{len(gastos)} gasto(s), "
                        f"C${totales['total_ventas']:.2f} en ventas"
                    ),
                    antes={
                        "caja_abierta": True,
                        "ordenes": totales["total_ordenes"],
                        "gastos": len(gastos),
                    },
                    despues={
                        "cierre_id": cierre.id,
                        "total_ventas": totales["total_ventas"],
                        "total_ordenes": totales["total_ordenes"],
                    },
                )

            self.config.guardar(self.CLAVE_ULTIMA_FECHA, fecha_cierre.date().isoformat())
            self.config.guardar(
                self.CLAVE_ULTIMA_EJECUCION, fecha_cierre.isoformat(timespec="seconds")
            )
            self.db.commit()
            self.db.refresh(cierre)
            return CierreCajaResponse.model_validate(cierre)

        except Exception as exc:
            self.db.rollback()
            print(f"[X] Error en cerrar_caja_automatica: {exc}")
            raise

    def _actor(self, usuario_id: int, username: str, rol: str):
        """Construye un objeto mínimo compatible con ``AuditoriaService.registrar``."""
        from types import SimpleNamespace

        return SimpleNamespace(id=usuario_id, username=username, rol=rol)
