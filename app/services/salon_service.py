from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.salon import EstadoMesa
from app.repositories.salon_repository import SalonRepository
from app.schemas.salon import (
    ZonaCreate,
    ZonaResponse,
    MesaCreate,
    MesaUpdate,
    MesaResponse
)


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
        zonas = self.salon_repo.obtener_zonas_con_mesas()
        return [ZonaResponse.model_validate(z) for z in zonas]

    def eliminar_zona(self, zona_id: int) -> None:
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

    def actualizar_mesa(self, mesa_id: int, mesa_in: MesaUpdate) -> MesaResponse:
        existente = self.salon_repo.obtener_mesa_por_id(mesa_id)
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la mesa con ID {mesa_id}"
            )

        update_data = mesa_in.model_dump(exclude_unset=True)

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
        self.salon_repo.eliminar_mesa(mesa_id)
