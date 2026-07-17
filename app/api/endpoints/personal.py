from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import requerir_rol
from app.core.database import get_db
from app.schemas.personal import (
    PuestoCreate,
    PuestoResponse,
    EmpleadoCreate,
    EmpleadoUpdate,
    EmpleadoResponse,
    UsuarioCreate,
    UsuarioResponse,
    PasswordResetRequest,
    RolEnum
)
from app.services.personal_service import PersonalService

router = APIRouter()


def get_personal_service(db: Session = Depends(get_db)) -> PersonalService:
    """
    Dependencia para inyectar el servicio de personal.

    Args:
        db: Sesión de base de datos.

    Returns:
        Instancia de PersonalService.
    """
    return PersonalService(db)


# =============================================================================
# Endpoints de Puestos
# =============================================================================

@router.post(
    "/puestos",
    response_model=PuestoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear puesto laboral",
    description="Registra un nuevo puesto laboral en el sistema. Solo Administradores y Gerentes.",
    tags=["Puestos"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def crear_puesto(
    puesto_in: PuestoCreate,
    service: PersonalService = Depends(get_personal_service)
) -> PuestoResponse:
    """
    Crea un nuevo puesto laboral.

    - **nombre**: Nombre único del puesto (ej: "Chef", "Mesero")
    - **salario_base**: Salario base del puesto (debe ser mayor a 0)
    """
    return service.crear_puesto(puesto_in)


@router.get(
    "/puestos",
    response_model=List[PuestoResponse],
    summary="Listar puestos",
    description="Obtiene la lista de todos los puestos registrados.",
    tags=["Puestos"]
)
def listar_puestos(
    service: PersonalService = Depends(get_personal_service)
) -> List[PuestoResponse]:
    """
    Retorna la lista de todos los puestos laborales.
    """
    return service.listar_puestos()


# =============================================================================
# Endpoints de Empleados
# =============================================================================

@router.post(
    "/empleados",
    response_model=EmpleadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar empleado",
    description="Registra un nuevo empleado en el restaurante. Solo Administradores y Gerentes.",
    tags=["Empleados"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def registrar_empleado(
    empleado_in: EmpleadoCreate,
    service: PersonalService = Depends(get_personal_service)
) -> EmpleadoResponse:
    """
    Registra un nuevo empleado.

    - **nombre**: Nombre del empleado
    - **apellido**: Apellido del empleado
    - **cedula_identidad**: Cédula única de identidad
    - **puesto_id**: ID del puesto a asignar
    """
    return service.registrar_empleado(empleado_in)


@router.get(
    "/empleados",
    response_model=List[EmpleadoResponse],
    summary="Listar empleados activos",
    description="Obtiene la lista de empleados activos del restaurante.",
    tags=["Empleados"]
)
def listar_empleados(
    service: PersonalService = Depends(get_personal_service)
) -> List[EmpleadoResponse]:
    """
    Retorna la lista de empleados activos.
    """
    return service.listar_empleados(solo_activos=True)


@router.put(
    "/empleados/{empleado_id}",
    response_model=EmpleadoResponse,
    summary="Actualizar empleado",
    description="Actualiza datos de un empleado existente (nombre, apellido, teléfono, puesto, salario, estado). Solo Administradores y Gerentes.",
    tags=["Empleados"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def editar_empleado(
    empleado_id: int,
    empleado_in: EmpleadoUpdate,
    service: PersonalService = Depends(get_personal_service)
) -> EmpleadoResponse:
    """
    Actualiza los campos enviados de un empleado.
    """
    return service.editar_empleado(empleado_id, empleado_in)


# =============================================================================
# Endpoints de Usuarios
# =============================================================================

@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario del sistema",
    description="Registra un nuevo usuario para acceder al sistema. Solo Administradores y Gerentes.",
    tags=["Usuarios"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def crear_usuario(
    usuario_in: UsuarioCreate,
    service: PersonalService = Depends(get_personal_service)
) -> UsuarioResponse:
    """
    Crea un nuevo usuario del sistema.

    - **username**: Nombre de usuario único
    - **password**: Contraseña (mínimo 6 caracteres)
    - **rol**: Rol del usuario (Administrador, Gerente, Vendedor)
    - **empleado_id**: ID del empleado asociado (debe estar activo)
    """
    return service.crear_usuario_sistema(usuario_in)


@router.get(
    "/usuarios",
    response_model=List[UsuarioResponse],
    summary="Listar usuarios",
    description="Obtiene la lista de todos los usuarios registrados.",
    tags=["Usuarios"]
)
def listar_usuarios(
    service: PersonalService = Depends(get_personal_service)
) -> List[UsuarioResponse]:
    """
    Retorna la lista de todos los usuarios del sistema.
    """
    return service.listar_usuarios()


@router.put(
    "/usuarios/{usuario_id}/reset-password",
    response_model=UsuarioResponse,
    summary="Restablecer contraseña de usuario",
    description="Actualiza la contraseña de un usuario existente. Solo Administradores y Gerentes.",
    tags=["Usuarios"],
    dependencies=[Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))]
)
def restablecer_contrasena(
    usuario_id: int,
    request: PasswordResetRequest,
    service: PersonalService = Depends(get_personal_service)
) -> UsuarioResponse:
    """
    Restablece la contraseña de un usuario.

    - **usuario_id**: ID del usuario
    - **nueva_password**: Nueva contraseña (mínimo 6 caracteres)
    """
    return service.restablecer_contrasena(usuario_id, request)
