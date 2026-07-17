from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.personal import Puesto, Empleado, Usuario
from app.repositories.base_repository import BaseRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.repositories.empleado_repository import EmpleadoRepository
from app.schemas.personal import (
    PuestoCreate,
    PuestoResponse,
    EmpleadoCreate,
    EmpleadoUpdate,
    EmpleadoResponse,
    UsuarioCreate,
    UsuarioResponse,
    PasswordResetRequest
)
from app.core.security import obtener_password_hash


class PersonalService:
    """
    Servicio de lógica de negocio para el módulo de personal.

    Coordina las operaciones entre repositorios, validaciones
    y reglas de negocio del sistema.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.puesto_repo = BaseRepository(Puesto, db)
        self.empleado_repo = EmpleadoRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    # =========================================================================
    # Puestos
    # =========================================================================

    def crear_puesto(self, puesto_in: PuestoCreate) -> PuestoResponse:
        """
        Crea un nuevo puesto laboral.

        Args:
            puesto_in: Datos del puesto a crear.

        Returns:
            PuestoResponse con el puesto creado.

        Raises:
            HTTPException 400: Si ya existe un puesto con ese nombre.
        """
        existente = self._buscar_puesto_por_nombre(puesto_in.nombre)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un puesto con el nombre '{puesto_in.nombre}'"
            )

        puesto_data = puesto_in.model_dump()
        puesto_creado = self.puesto_repo.create(puesto_data)
        return PuestoResponse.model_validate(puesto_creado)

    def obtener_puesto(self, puesto_id: int) -> PuestoResponse:
        """
        Obtiene un puesto por su ID.

        Args:
            puesto_id: ID del puesto.

        Returns:
            PuestoResponse con los datos del puesto.

        Raises:
            HTTPException 404: Si el puesto no existe.
        """
        puesto = self.puesto_repo.get_by_id(puesto_id)
        if not puesto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el puesto con ID {puesto_id}"
            )
        return PuestoResponse.model_validate(puesto)

    def listar_puestos(self) -> List[PuestoResponse]:
        """
        Lista todos los puestos registrados.

        Returns:
            Lista de PuestoResponse.
        """
        puestos = self.puesto_repo.get_all()
        return [PuestoResponse.model_validate(p) for p in puestos]

    # =========================================================================
    # Empleados
    # =========================================================================

    def registrar_empleado(self, empleado_in: EmpleadoCreate) -> EmpleadoResponse:
        """
        Registra un nuevo empleado en el sistema.

        Args:
            empleado_in: Datos del empleado a registrar.

        Returns:
            EmpleadoResponse con el empleado registrado.

        Raises:
            HTTPException 404: Si el puesto_id no existe.
            HTTPException 400: Si la cédula ya está registrada.
        """
        puesto = self.puesto_repo.get_by_id(empleado_in.puesto_id)
        if not puesto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el puesto con ID {empleado_in.puesto_id}"
            )

        if self.empleado_repo.exists_by_cedula(empleado_in.cedula_identidad):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un empleado con la cédula '{empleado_in.cedula_identidad}'"
            )

        empleado_data = empleado_in.model_dump()
        empleado_creado = self.empleado_repo.create(empleado_data)
        return EmpleadoResponse.model_validate(empleado_creado)

    def obtener_empleado(self, empleado_id: int) -> EmpleadoResponse:
        """
        Obtiene un empleado por su ID.

        Args:
            empleado_id: ID del empleado.

        Returns:
            EmpleadoResponse con los datos del empleado.

        Raises:
            HTTPException 404: Si el empleado no existe.
        """
        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )
        return EmpleadoResponse.model_validate(empleado)

    def listar_empleados(self, solo_activos: bool = False) -> List[EmpleadoResponse]:
        """
        Lista todos los empleados registrados.

        Args:
            solo_activos: Si es True, solo retorna empleados activos.

        Returns:
            Lista de EmpleadoResponse.
        """
        if solo_activos:
            empleados = self.empleado_repo.get_activos()
        else:
            empleados = self.empleado_repo.get_all()
        return [EmpleadoResponse.model_validate(e) for e in empleados]

    def desactivar_empleado(self, empleado_id: int) -> EmpleadoResponse:
        """
        Desactiva un empleado (baja lógica).

        Args:
            empleado_id: ID del empleado a desactivar.

        Returns:
            EmpleadoResponse con el empleado desactivado.

        Raises:
            HTTPException 404: Si el empleado no existe.
        """
        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )

        empleado_desactivado = self.empleado_repo.desactivar(empleado_id)
        return EmpleadoResponse.model_validate(empleado_desactivado)

    def editar_empleado(
        self, empleado_id: int, empleado_in: EmpleadoUpdate
    ) -> EmpleadoResponse:
        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )

        update_data = empleado_in.model_dump(exclude_unset=True)

        if "puesto_id" in update_data:
            puesto = self.puesto_repo.get_by_id(update_data["puesto_id"])
            if not puesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontró el puesto con ID {update_data['puesto_id']}"
                )

        if update_data:
            self.empleado_repo.update(empleado_id, update_data)

        updated = self.empleado_repo.get_by_id(empleado_id)
        return EmpleadoResponse.model_validate(updated)

    # =========================================================================
    # Usuarios del Sistema
    # =========================================================================

    def crear_usuario_sistema(self, usuario_in: UsuarioCreate) -> UsuarioResponse:
        """
        Crea un nuevo usuario del sistema.

        Args:
            usuario_in: Datos del usuario a crear.

        Returns:
            UsuarioResponse con el usuario creado.

        Raises:
            HTTPException 404: Si el empleado_id no existe o está inactivo.
            HTTPException 400: Si el username ya está en uso.
        """
        empleado = self.empleado_repo.get_by_id(usuario_in.empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {usuario_in.empleado_id}"
            )

        if not empleado.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El empleado con ID {usuario_in.empleado_id} no está activo"
            )

        if self.usuario_repo.exists_by_username(usuario_in.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El nombre de usuario '{usuario_in.username}' ya está en uso"
            )

        usuario_data = usuario_in.model_dump()
        password_plano = usuario_data.pop("password")
        usuario_data["password_hash"] = obtener_password_hash(password_plano)

        usuario_creado = self.usuario_repo.create(usuario_data)
        return UsuarioResponse.model_validate(usuario_creado)

    def obtener_usuario(self, usuario_id: int) -> UsuarioResponse:
        """
        Obtiene un usuario por su ID.

        Args:
            usuario_id: ID del usuario.

        Returns:
            UsuarioResponse con los datos del usuario.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = self.usuario_repo.get_by_id(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el usuario con ID {usuario_id}"
            )
        return UsuarioResponse.model_validate(usuario)

    def listar_usuarios(self) -> List[UsuarioResponse]:
        """
        Lista todos los usuarios registrados.

        Returns:
            Lista de UsuarioResponse.
        """
        usuarios = self.usuario_repo.get_all()
        return [UsuarioResponse.model_validate(u) for u in usuarios]

    def restablecer_contrasena(
        self,
        usuario_id: int,
        request: PasswordResetRequest
    ) -> UsuarioResponse:
        """
        Restablece la contraseña de un usuario.

        Args:
            usuario_id: ID del usuario.
            request: Solicitud con la nueva contraseña.

        Returns:
            UsuarioResponse con el usuario actualizado.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = self.usuario_repo.get_by_id(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el usuario con ID {usuario_id}"
            )

        nuevo_hash = obtener_password_hash(request.nueva_password)
        self.usuario_repo.update(usuario_id, {"password_hash": nuevo_hash})
        return UsuarioResponse.model_validate(
            self.usuario_repo.get_by_id(usuario_id)
        )

    # =========================================================================
    # Métodos Privados de Validación
    # =========================================================================

    def _buscar_puesto_por_nombre(self, nombre: str) -> Optional[Puesto]:
        """
        Busca un puesto por su nombre.

        Args:
            nombre: Nombre del puesto a buscar.

        Returns:
            El puesto encontrado o None.
        """
        from sqlalchemy import select
        statement = select(Puesto).where(Puesto.nombre == nombre)
        return self.db.execute(statement).scalar_one_or_none()
