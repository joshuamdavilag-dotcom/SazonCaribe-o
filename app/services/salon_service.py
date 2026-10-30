import re
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orden import EstadoOrden, Orden
from app.models.personal import Usuario
from app.models.salon import EstadoMesa, Mesa
from app.repositories.salon_repository import SalonRepository
from app.schemas.salon import (
    ZonaCreate,
    ZonaResponse,
    MesaCreate,
    MesaUpdate,
    MesaResponse,
    FusionMesasResponse
)
from app.services.auditoria_service import AuditoriaService


PALETA_FUSION = (
    "#2A9D8F",
    "#E63946",
    "#FFB703",
    "#003366",
    "#7C3AED",
    "#0EA5E9",
    "#EA580C",
    "#059669",
)
_RE_COLOR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class SalonService:
    """
    Servicio de lógica de negocio para el módulo de salón.

    Coordina las operaciones de zonas, mesas
    y la gestión de estados del restaurante.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.salon_repo = SalonRepository(db)

    # =========================================================================
    # Gestión de Zonas
    # =========================================================================

    def crear_zona(
        self,
        zona_in: ZonaCreate
    ) -> ZonaResponse:
        """
        Crea una nueva zona en el restaurante.

        Args:
            zona_in: Datos de la zona a crear.

        Returns:
            ZonaResponse con la zona creada.

        Raises:
            HTTPException 400: Si ya existe una zona con ese nombre.
        """
        zonas_existentes = self.salon_repo.obtener_zonas_con_mesas()
        for zona in zonas_existentes:
            if zona.nombre.lower() == zona_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una zona con el nombre '{zona_in.nombre}'"
                )

        zona_creada = self.salon_repo.crear_zona(zona_in)
        return ZonaResponse.model_validate(zona_creada)

    def obtener_mapa_completo(self) -> List[ZonaResponse]:
        """
        Obtiene el mapa completo del restaurante.

        Retorna todas las zonas con sus mesas asociadas,
        incluyendo el estado actual de cada mesa.

        Returns:
            Lista de ZonaResponse con las mesas precargadas.
        """
        zonas = self.salon_repo.obtener_zonas_con_mesas()
        return [ZonaResponse.model_validate(z) for z in zonas]

    def listar_zonas(self) -> List[ZonaResponse]:
        """
        Lista todas las zonas del restaurante con sus mesas asociadas.

        Returns:
            Lista de ZonaResponse.
        """
        zonas = self.salon_repo.obtener_zonas_con_mesas()
        return [ZonaResponse.model_validate(z) for z in zonas]

    def eliminar_zona(self, zona_id: int) -> None:
        """
        Elimina una zona sin mesas asociadas.

        Raises:
            HTTPException 404: Si la zona no existe.
            HTTPException 400: Si la zona tiene mesas asociadas.
        """
        zona = self.salon_repo.obtener_zona_por_id(zona_id)
        if not zona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la zona con ID {zona_id}"
            )
        count = self.salon_repo.contar_mesas_por_zona(zona_id)
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar la zona '{zona.nombre}': tiene {count} mesa(s) asociada(s). Elimina o reasigna las mesas primero."
            )
        self.salon_repo.eliminar_zona(zona_id)

    # =========================================================================
    # Gestión de Mesas
    # =========================================================================

    def crear_mesa(
        self,
        mesa_in: MesaCreate
    ) -> MesaResponse:
        """
        Crea una nueva mesa en el restaurante.

        Flujo de validación:
        1. Verifica que la zona exista.
        2. Verifica que el número de mesa no exista en esa zona.
        3. Crea la mesa si todo es válido.

        Args:
            mesa_in: Datos de la mesa a crear.

        Returns:
            MesaResponse con la mesa creada.

        Raises:
            HTTPException 404: Si la zona no existe.
            HTTPException 400: Si ya existe una mesa con ese número en la zona.
        """
        zona = self.salon_repo.obtener_zona_por_id(mesa_in.zona_id)
        if not zona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La zona especificada no existe"
            )

        for mesa_existente in zona.mesas:
            if mesa_existente.numero == mesa_in.numero:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La mesa número {mesa_in.numero} ya existe en esta zona"
                )

        mesa_creada = self.salon_repo.crear_mesa(mesa_in)
        return MesaResponse.model_validate(mesa_creada)

    def obtener_mesas(
        self,
        estados: Optional[List[EstadoMesa]] = None
    ) -> List[MesaResponse]:
        """
        Obtiene las mesas del restaurante.

        Args:
            estados: Lista de estados para filtrar (opcional).

        Returns:
            Lista de MesaResponse.
        """
        mesas = self.salon_repo.obtener_mesas_filtradas(estados)
        return [MesaResponse.model_validate(m) for m in mesas]

    def cambiar_estado_mesa(
        self,
        mesa_id: int,
        nuevo_estado: EstadoMesa
    ) -> MesaResponse:
        """Cambia el estado de una mesa (LIBRE, OCUPADA, RESERVADA, MANTENIMIENTO).

        Las mesas fusionadas no se liberan de forma individual con una comanda
        activa: para eso existe la separación de fusiones o el cobro de la cuenta.

        Raises:
            HTTPException 404: Si la mesa no existe.
            HTTPException 400: Si la mesa está fusionada con una comanda activa.
        """
        existente = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )

        if nuevo_estado == EstadoMesa.LIBRE and existente.grupo_fusion_id:
            grupo = self.salon_repo.obtener_mesas_por_grupo(existente.grupo_fusion_id)
            if self._orden_activa_del_grupo(grupo):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "La mesa pertenece a una fusión con una comanda activa. "
                        "Cobre la cuenta o separe la fusión antes de liberarla."
                    )
                )
            self._disolver_grupo(grupo)

        mesa_actualizada = self.salon_repo.actualizar_estado_mesa(
            mesa_id,
            nuevo_estado
        )

        if not mesa_actualizada:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )

        return MesaResponse.model_validate(mesa_actualizada)

    def asignar_apodo_mesa(
        self,
        mesa_id: int,
        apodo: Optional[str]
    ) -> MesaResponse:
        """
        Asigna un apodo temporal a una mesa ocupada.

        El apodo se usa para rastrear al cliente si se movió de mesa
        (ej: "Mesa 1" → "Juan"). Solo aplica a mesas OCUPADA y se limpia
        automáticamente cuando la mesa vuelve a LIBRE.

        Args:
            mesa_id: ID de la mesa.
            apodo: Apodo a asignar; vacío o None limpia el apodo.

        Raises:
            HTTPException 404: Si la mesa no existe.
            HTTPException 400: Si la mesa no está ocupada.
        """
        mesa = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not mesa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )
        if mesa.estado != EstadoMesa.OCUPADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede asignar un apodo a mesas ocupadas"
            )

        apodo_limpio = apodo.strip() if apodo else None
        if apodo_limpio == "":
            apodo_limpio = None

        mesa_actualizada = self.salon_repo.asignar_apodo(mesa_id, apodo_limpio)
        return MesaResponse.model_validate(mesa_actualizada)

    def actualizar_mesa(self, mesa_id: int, mesa_in: MesaUpdate) -> MesaResponse:
        """
        Actualiza los datos de una mesa.

        Valida que la zona destino exista y que el número no se repita dentro
        de la zona.

        Args:
            mesa_id: ID de la mesa.
            mesa_in: Campos a actualizar.

        Returns:
            MesaResponse con la mesa actualizada.

        Raises:
            HTTPException 404: Si la mesa o la zona indicada no existen.
            HTTPException 400: Si el número de mesa ya existe en la zona.
        """
        existente = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )

        update_data = mesa_in.model_dump(exclude_unset=True)

        if update_data.get("estado") == EstadoMesa.LIBRE and existente.grupo_fusion_id:
            grupo = self.salon_repo.obtener_mesas_por_grupo(existente.grupo_fusion_id)
            if self._orden_activa_del_grupo(grupo):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "La mesa pertenece a una fusión con una comanda activa. "
                        "Cobre la cuenta o separe la fusión antes de liberarla."
                    )
                )
            self._disolver_grupo(grupo)

        if "zona_id" in update_data:
            zona = self.salon_repo.obtener_zona_por_id(update_data["zona_id"])
            if not zona:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La zona especificada no existe"
                )

        if "numero" in update_data:
            zona_id = update_data.get("zona_id", existente.zona_id)
            for m in (self.salon_repo.obtener_zona_por_id(zona_id).mesas or []):
                if m.numero == update_data["numero"] and m.id != mesa_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"La mesa número {update_data['numero']} ya existe en esta zona"
                    )

        mesa_actualizada = self.salon_repo.actualizar_mesa(mesa_id, **update_data)
        return MesaResponse.model_validate(mesa_actualizada)

    def eliminar_mesa(self, mesa_id: int) -> None:
        """
        Elimina una mesa que no esté ocupada.

        Raises:
            HTTPException 404: Si la mesa no existe.
            HTTPException 400: Si la mesa está ocupada.
        """
        existente = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )
        if existente.estado == EstadoMesa.OCUPADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar una mesa que está ocupada"
            )
        if existente.grupo_fusion_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar una mesa fusionada. Separe la fusión primero."
            )
        self.salon_repo.eliminar_mesa(mesa_id)

    # =========================================================================
    # Fusión de mesas
    # =========================================================================

    def _orden_activa_del_grupo(self, mesas: List[Mesa]) -> Optional[Orden]:
        """Devuelve la comanda activa de cualquiera de las mesas del grupo."""
        ids = [m.id for m in mesas if m.id]
        if not ids:
            return None
        statement = (
            select(Orden)
            .where(
                Orden.mesa_id.in_(ids),
                Orden.estado.in_(
                    (EstadoOrden.PENDIENTE, EstadoOrden.PREPARANDO, EstadoOrden.ENTREGADA)
                ),
                Orden.anulada.is_(False),
            )
            .order_by(Orden.fecha_creacion, Orden.id)
        )
        return self.db.execute(statement).scalars().first()

    def _color_fusion_libre(self, grupo_fusion_id: Optional[str] = None) -> str:
        """Elige un color de la paleta que no esté usado por otro grupo."""
        en_uso = set(self.salon_repo.obtener_colores_fusion_en_uso(grupo_fusion_id))
        for color in PALETA_FUSION:
            if color.lower() not in {c.lower() for c in en_uso}:
                return color
        return PALETA_FUSION[len(en_uso) % len(PALETA_FUSION)]

    def _disolver_grupo(self, mesas: List[Mesa]) -> None:
        """Libera todas las mesas del grupo y borra su marca de fusión."""
        for mesa in mesas:
            mesa.estado = EstadoMesa.LIBRE
            mesa.apodo = None
            mesa.grupo_fusion_id = None
            mesa.color_fusion = None
            mesa.mesa_principal_id = None

    def _recalcular_orden(self, orden: Orden) -> None:
        """Recalcula los totales de una orden a partir de sus líneas vigentes."""
        subtotal = Decimal("0.00")
        descuento_total = Decimal("0.00")
        for detalle in orden.detalles:
            vigentes = detalle.cantidad - (detalle.cantidad_devuelta or 0)
            if vigentes <= 0:
                continue
            subtotal += Decimal(str(detalle.precio_unitario)) * vigentes
            descuento_linea = detalle.descuento_monto or Decimal("0.00")
            if detalle.cantidad_devuelta and detalle.cantidad:
                proporcion = Decimal(vigentes) / Decimal(detalle.cantidad)
                descuento_linea = (descuento_linea * proporcion).quantize(Decimal("0.01"))
            descuento_total += descuento_linea
        orden.subtotal = subtotal
        orden.descuento_total = descuento_total
        orden.total = max(subtotal - descuento_total, Decimal("0.00"))

    def _consolidar_ordenes(self, principal: Mesa, mesas: List[Mesa]) -> Optional[Orden]:
        """Unifica las comandas activas de las mesas en una sola orden.

        La orden resultante queda ligada a la mesa principal. Los ítems de las
        demás órdenes se mueven sin tocar inventario (el stock ya se descontó
        cuando se crearon) y las órdenes vacías se eliminan.
        """
        ordenes = []
        ids = [m.id for m in mesas]
        statement = (
            select(Orden)
            .where(
                Orden.mesa_id.in_(ids),
                Orden.estado.in_(
                    (EstadoOrden.PENDIENTE, EstadoOrden.PREPARANDO, EstadoOrden.ENTREGADA)
                ),
                Orden.anulada.is_(False),
            )
            .order_by(Orden.fecha_creacion, Orden.id)
        )
        ordenes = list(self.db.execute(statement).scalars().all())
        if not ordenes:
            return None

        destino = next((o for o in ordenes if o.mesa_id == principal.id), ordenes[0])
        for orden in ordenes:
            if orden.id == destino.id:
                continue
            for detalle in list(orden.detalles):
                detalle.orden = destino
            self.db.delete(orden)

        destino.mesa_id = principal.id
        self.db.flush()
        self.db.refresh(destino)
        self._recalcular_orden(destino)
        return destino

    def fusionar_mesas(
        self,
        mesa_ids: List[int],
        color: Optional[str] = None,
        actor: Optional[Usuario] = None,
    ) -> FusionMesasResponse:
        """Fusiona dos o más mesas en un grupo con color propio.

        Reglas:
        - Al menos una mesa debe tener una comanda activa (la fusión implica
          clientes presentes y las mesas quedan OCUPADA).
        - No se pueden fusionar mesas de dos grupos distintos.
        - Solo se aceptan mesas LIBRE u OCUPADA.
        - Las comandas activas se consolidan en una sola orden ligada a la
          mesa principal; el resto de mesas queda OCUPADA mostrando ese color.

        Raises:
            HTTPException 400/404: datos inválidos o mesas inexistentes.
        """
        ids = list(dict.fromkeys(mesa_ids))
        if len(ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se necesitan al menos dos mesas para fusionar."
            )
        if color is not None and not _RE_COLOR_HEX.match(color):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El color de fusión debe tener formato hexadecimal (#RRGGBB)."
            )

        mesas = self.salon_repo.obtener_mesas_por_ids(ids)
        if len(mesas) != len(ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Una o más mesas seleccionadas no existen."
            )

        invalidas = [m for m in mesas if m.estado not in (EstadoMesa.LIBRE, EstadoMesa.OCUPADA)]
        if invalidas:
            numeros = ", ".join(str(m.numero) for m in invalidas)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Las mesas {numeros} no se pueden fusionar en su estado actual."
            )

        grupos = {m.grupo_fusion_id for m in mesas if m.grupo_fusion_id}
        if len(grupos) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Las mesas seleccionadas pertenecen a fusiones distintas. "
                    "Separe las fusiones actuales antes de unirlas."
                )
            )
        grupo_existente = grupos.pop() if grupos else None
        grupo_fusion_id = grupo_existente or uuid4().hex

        orden_activa = self._orden_activa_del_grupo(mesas)
        if not orden_activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ninguna de las mesas seleccionadas tiene una comanda activa. "
                    "Abra la comanda en una mesa y vuelva a fusionar."
                )
            )

        if grupo_existente:
            miembros = self.salon_repo.obtener_mesas_por_grupo(grupo_existente)
            principal = next(
                (m for m in miembros if m.mesa_principal_id is None),
                miembros[0],
            )
        else:
            principal = next(m for m in mesas if m.id == orden_activa.mesa_id)

        color_final = color or self._color_fusion_libre(grupo_existente)

        pertenecientes = {m.id: m for m in mesas}
        if grupo_existente:
            for mesa in self.salon_repo.obtener_mesas_por_grupo(grupo_existente):
                pertenecientes.setdefault(mesa.id, mesa)

        orden = self._consolidar_ordenes(principal, list(pertenecientes.values()))

        for mesa in pertenecientes.values():
            mesa.grupo_fusion_id = grupo_fusion_id
            mesa.color_fusion = color_final
            mesa.mesa_principal_id = None if mesa.id == principal.id else principal.id
            mesa.estado = EstadoMesa.OCUPADA

        if actor is not None:
            AuditoriaService.registrar(
                self.db,
                actor,
                "MESAS_FUSIONADAS",
                "mesa",
                principal.id,
                f"Fusión de mesas {', '.join(str(m.numero) for m in pertenecientes.values())}",
                antes={"mesas": ids},
                despues={
                    "grupo_fusion_id": grupo_fusion_id,
                    "color_fusion": color_final,
                    "mesa_principal_id": principal.id,
                    "orden_id": orden.id if orden else None,
                },
            )

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        mesas_actualizadas = self.salon_repo.obtener_mesas_por_grupo(grupo_fusion_id)
        return FusionMesasResponse(
            grupo_fusion_id=grupo_fusion_id,
            color_fusion=color_final,
            mesa_principal_id=principal.id,
            orden_id=orden.id if orden else None,
            mesas=[MesaResponse.model_validate(m) for m in mesas_actualizadas],
            mensaje=(
                f"Mesas {', '.join(str(m.numero) for m in mesas_actualizadas)} "
                "fusionadas correctamente."
            ),
        )

    def separar_mesa(
        self,
        mesa_id: int,
        actor: Optional[Usuario] = None,
    ) -> FusionMesasResponse:
        """Saca una mesa de su grupo de fusión.

        Si la mesa separada era la principal, otra mesa asume como principal y
        la comanda la sigue. La mesa separada queda LIBRE. Si el grupo queda con
        una sola mesa, la fusión se disuelve.
        """
        mesa = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not mesa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )
        if not mesa.grupo_fusion_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La mesa no está fusionada."
            )

        grupo_id = mesa.grupo_fusion_id
        grupo = self.salon_repo.obtener_mesas_por_grupo(grupo_id)
        orden = self._orden_activa_del_grupo(grupo)
        restantes = [m for m in grupo if m.id != mesa.id]
        era_principal = mesa.mesa_principal_id is None

        if len(restantes) < 2:
            restante = restantes[0] if restantes else None
            apodo_heredado = mesa.apodo
            if orden and restante is not None:
                orden.mesa_id = restante.id
            self._disolver_grupo(grupo)
            if restante is not None:
                restante.estado = EstadoMesa.OCUPADA if orden else EstadoMesa.LIBRE
                restante.apodo = apodo_heredado if orden else None
            grupo_final: List[Mesa] = restantes
            principal_id = restante.id if restante is not None else None
            color = None
        else:
            if era_principal:
                nuevo_principal = restantes[0]
                for miembro in restantes:
                    miembro.mesa_principal_id = (
                        None if miembro.id == nuevo_principal.id else nuevo_principal.id
                    )
                if orden:
                    orden.mesa_id = nuevo_principal.id
                principal_id = nuevo_principal.id
            else:
                principal_id = next(
                    (m.id for m in restantes if m.mesa_principal_id is None),
                    restantes[0].id,
                )
            mesa.estado = EstadoMesa.LIBRE
            mesa.apodo = None
            mesa.grupo_fusion_id = None
            mesa.color_fusion = None
            mesa.mesa_principal_id = None
            grupo_final = restantes
            color = restantes[0].color_fusion if restantes else None

        if actor is not None:
            AuditoriaService.registrar(
                self.db,
                actor,
                "MESAS_SEPARADAS",
                "mesa",
                mesa_id,
                f"Mesa {mesa.numero} separada de la fusión",
                antes={"grupo_fusion_id": grupo_id},
                despues={
                    "grupo_fusion_id": grupo_final[0].grupo_fusion_id if grupo_final else None,
                    "mesa_principal_id": principal_id,
                },
            )

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return FusionMesasResponse(
            grupo_fusion_id=grupo_final[0].grupo_fusion_id if grupo_final else None,
            color_fusion=color,
            mesa_principal_id=principal_id,
            orden_id=orden.id if orden else None,
            mesas=[MesaResponse.model_validate(m) for m in grupo_final],
            mensaje=f"Mesa {mesa.numero} separada de la fusión.",
        )

    def liberar_grupo_fusion(self, mesa_id: int) -> None:
        """Libera todas las mesas del grupo al cobrar o cancelar la cuenta.

        No hace commit: lo controla el llamador (``OrdenService``) dentro de su
        propia transacción.
        """
        mesa = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not mesa or not mesa.grupo_fusion_id:
            return
        grupo = self.salon_repo.obtener_mesas_por_grupo(mesa.grupo_fusion_id)
        self._disolver_grupo(grupo)
