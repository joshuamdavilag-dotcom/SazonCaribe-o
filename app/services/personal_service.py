from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.personal import Puesto, Empleado, Usuario
from app.models.orden import Orden
from app.models.gasto import Gasto
from app.models.asistencia import Asistencia
from app.models.nomina import Nomina, AdelantoSalario
from app.models.inventario import PreparacionCocina
from app.models.caja import CierreCaja
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
    PasswordResetRequest,
    EliminarEmpleadoRequest,
    RolEnum,
)
from app.core.security import obtener_password_hash, verificar_password
from app.services.asistencia_service import AsistenciaService


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

    def dar_de_baja_empleado(
        self,
        empleado_id: int,
        request: EliminarEmpleadoRequest,
        current_user: Usuario,
    ) -> EmpleadoResponse:
        """
        Da de baja a un empleado (borrado lógico) con autorización por contraseña.

        Valida la contraseña del usuario autenticado contra su hash antes de
        desactivar al empleado. También desactiva el usuario del sistema
        vinculado para impedir que siga iniciando sesión. Los registros
        históricos de asistencia y nómina se conservan.

        Args:
            empleado_id: ID del empleado a dar de baja.
            request: Solicitud con la contraseña del usuario en sesión.
            current_user: Usuario autenticado (Admin/Gerente).

        Returns:
            EmpleadoResponse con el empleado desactivado.

        Raises:
            HTTPException 404: Si el empleado no existe.
            HTTPException 400: Si ya está inactivo o es el propio usuario.
            HTTPException 401: Si la contraseña es incorrecta.
        """
        empleado = self.empleado_repo.get_by_id(empleado_id)
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el empleado con ID {empleado_id}"
            )

        if not empleado.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El empleado ya está inactivo"
            )

        if current_user.empleado_id == empleado_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes dar de baja a tu propio usuario"
            )

        if not verificar_password(request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña incorrecta"
            )

        usuario = self.usuario_repo.get_by_empleado_id(empleado_id)
        if usuario and usuario.activo:
            self.usuario_repo.update(usuario.id, {"activo": False})

        empleado_desactivado = self.empleado_repo.desactivar(empleado_id)
        return EmpleadoResponse.model_validate(empleado_desactivado)

    def eliminar_usuario(
        self,
        usuario_id: int,
        request: EliminarEmpleadoRequest,
        current_user: Usuario,
    ) -> dict:
        """
        Elimina un usuario (y su empleado vinculado) liberando su username.

        Regla de reutilización:
        1. Si NI el usuario NI su empleado tienen registros asociados
           (órdenes, gastos, asistencias, nóminas, adelantos, preparaciones
           de cocina o cierres de caja), elimina físicamente ambos registros.
        2. Si tienen registros contables, los archiva: renombra username y
           cédula a ``{valor}_deleted_{id}`` y desactiva usuario y empleado
           (``activo = False``). Así el username y la cédula quedan
           disponibles para volver a registrar al empleado.

        Requiere la contraseña del usuario en sesión (Admin/Gerente).

        Args:
            usuario_id: ID del usuario a eliminar.
            request: Solicitud con la contraseña del usuario en sesión.
            current_user: Usuario autenticado (Admin/Gerente).

        Returns:
            Dict con ``resultado`` ('eliminado' | 'archivado') y ``mensaje``.

        Raises:
            HTTPException 404: Si el usuario no existe.
            HTTPException 400: Si es el propio usuario o ya fue eliminado.
            HTTPException 401: Si la contraseña es incorrecta.
        """
        usuario = self.usuario_repo.get_by_id(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el usuario con ID {usuario_id}"
            )

        if current_user.id == usuario_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes eliminar tu propio usuario"
            )

        if not verificar_password(request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña incorrecta"
            )

        sufijo = f"_deleted_{usuario_id}"
        if not usuario.activo and usuario.username.endswith(sufijo):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este usuario ya fue eliminado"
            )

        empleado = (
            self.empleado_repo.get_by_id(usuario.empleado_id)
            if usuario.empleado_id else None
        )
        tiene_refs_usuario = self._usuario_tiene_referencias(usuario_id)
        tiene_refs_empleado = (
            self._empleado_tiene_referencias(usuario.empleado_id)
            if usuario.empleado_id else False
        )

        if not tiene_refs_usuario and not tiene_refs_empleado:
            self.usuario_repo.delete(usuario_id)
            if empleado is not None:
                self.empleado_repo.delete(empleado.id)
            return {
                "resultado": "eliminado",
                "mensaje": (
                    f"El usuario '{usuario.username}' y su empleado fueron "
                    f"eliminados porque no tienen registros asociados."
                ),
            }

        nuevo_username = self._nombre_archivado(usuario.username, usuario_id, 50)
        self.usuario_repo.update(usuario_id, {
            "username": nuevo_username,
            "activo": False,
        })

        if empleado is not None:
            nueva_cedula = self._nombre_archivado(
                empleado.cedula_identidad, empleado.id, 20
            )
            self.empleado_repo.update(empleado.id, {
                "cedula_identidad": nueva_cedula,
                "activo": False,
            })
            mensaje = (
                f"El usuario '{usuario.username}' fue archivado como "
                f"'{nuevo_username}' y su empleado {empleado.nombre} fue "
                f"desactivado. El username y la cédula quedaron disponibles "
                f"para recontratar."
            )
        else:
            mensaje = (
                f"El usuario '{usuario.username}' fue archivado como "
                f"'{nuevo_username}' y desactivado. El username quedó "
                f"disponible para recontratar."
            )

        return {"resultado": "archivado", "mensaje": mensaje}

    def _usuario_tiene_referencias(self, usuario_id: int) -> bool:
        """
        Verifica si algún registro de otra tabla apunta al usuario.

        Evita borrar físicamente un usuario con actividad asociada
        (''referenced by'' de las FKs hacia ``usuarios.id``).

        Args:
            usuario_id: ID del usuario.

        Returns:
            True si existe al menos una referencia.
        """
        tablas = [
            (Orden, Orden.mesero_id),
            (Gasto, Gasto.registrado_por),
            (Asistencia, Asistencia.modificado_por),
            (AdelantoSalario, AdelantoSalario.registrado_por_id),
            (PreparacionCocina, PreparacionCocina.registrado_por),
            (CierreCaja, CierreCaja.cerrado_por),
        ]
        return self._alguna_referencia(usuario_id, tablas)

    def _empleado_tiene_referencias(self, empleado_id: int) -> bool:
        """
        Verifica si el empleado tiene registros contables (asistencias,
        nóminas o adelantos) que impiden su borrado físico.

        Args:
            empleado_id: ID del empleado.

        Returns:
            True si existe al menos una referencia.
        """
        tablas = [
            (Asistencia, Asistencia.empleado_id),
            (Nomina, Nomina.empleado_id),
            (AdelantoSalario, AdelantoSalario.empleado_id),
        ]
        return self._alguna_referencia(empleado_id, tablas)

    def _alguna_referencia(self, pk: int, tablas) -> bool:
        """
        Implementación compartida de conteo de FKs.

        Args:
            pk: ID a buscar en las columnas FK.
            tablas: Lista de tuplas (modelo, columna_fk).

        Returns:
            True si alguna tabla tiene un registro con esa FK.
        """
        for modelo, columna in tablas:
            statement = (
                select(func.count())
                .select_from(modelo)
                .where(columna == pk)
            )
            if self.db.execute(statement).scalar_one() > 0:
                return True
        return False

    def _nombre_archivado(self, valor: str, pk: int, max_len: int) -> str:
        """
        Genera el nombre archivado ``{valor}_deleted_{pk}`` truncando la base
        para respetar el largo máximo de la columna.

        Args:
            valor: Nombre original (username o cédula).
            pk: ID del registro (sufijo de unicidad).
            max_len: Largo máximo de la columna.

        Returns:
            El nombre archivado, o el mismo valor si ya tenía el sufijo.
        """
        sufijo = f"_deleted_{pk}"
        if valor.endswith(sufijo):
            return valor
        parte = valor[: max_len - len(sufijo)].strip()
        return f"{parte}{sufijo}"

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

        if self.usuario_repo.exists_by_username(usuario_in.username.strip().lower()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El nombre de usuario '{usuario_in.username}' ya está en uso"
            )

        usuario_data = usuario_in.model_dump()
        usuario_data["username"] = usuario_data["username"].strip().lower()
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

    def cambiar_turno_habilitado(
        self,
        usuario_id: int,
        turno_habilitado: bool,
    ) -> UsuarioResponse:
        """
        Habilita o deshabilita el inicio de turno de un usuario Vendedor.

        Args:
            usuario_id: ID del usuario.
            turno_habilitado: Nuevo estado de habilitación.

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

        actualizado = self.usuario_repo.actualizar_turno_habilitado(
            usuario_id,
            turno_habilitado,
        )
        if not turno_habilitado and actualizado.rol == RolEnum.VENDEDOR.value:
            AsistenciaService(self.db).cerrar_asistencias_por_deshabilitacion(
                [actualizado.empleado_id],
            )
        return UsuarioResponse.model_validate(actualizado)

    def habilitar_turno_masivo(self, turno_habilitado: bool) -> dict:
        """
        Habilita o deshabilita el inicio de turno de todos los Vendedores.

        Args:
            turno_habilitado: Nuevo estado de habilitación.

        Returns:
            Dict con la cantidad de usuarios actualizados.
        """
        actualizados = self.usuario_repo.actualizar_turno_habilitado_masivo(
            turno_habilitado
        )
        if not turno_habilitado and actualizados > 0:
            vendedores = self.usuario_repo.get_by_rol(RolEnum.VENDEDOR.value)
            AsistenciaService(self.db).cerrar_asistencias_por_deshabilitacion(
                [u.empleado_id for u in vendedores],
            )
        return {"actualizados": actualizados}

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
