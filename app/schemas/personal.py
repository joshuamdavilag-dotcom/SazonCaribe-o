from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


def validar_password_bcrypt(password: str) -> str:
    if len(password.strip().encode("utf-8")) > 72:
        raise ValueError(
            "La contraseña no puede superar los 72 bytes UTF-8 que admite bcrypt"
        )
    return password


class RolEnum(str, Enum):
    """Roles válidos para los usuarios del sistema."""
    ADMINISTRADOR = "Administrador"
    GERENTE = "Gerente"
    VENDEDOR = "Vendedor"


# =============================================================================
# Puesto Schemas
# =============================================================================

class PuestoBase(BaseModel):
    """Esquema base para Puesto."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del puesto laboral",
        examples=["Chef"]
    )
    salario_base: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Salario base del puesto",
        examples=[1500.00]
    )


class PuestoCreate(PuestoBase):
    """Esquema para crear un Puesto."""
    pass


class PuestoResponse(PuestoBase):
    """Esquema de respuesta para Puesto."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del puesto"
    )


# =============================================================================
# Empleado Schemas
# =============================================================================

class EmpleadoBase(BaseModel):
    """Esquema base para Empleado."""
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del empleado",
        examples=["Juan"]
    )
    apellido: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Apellido del empleado",
        examples=["Pérez"]
    )
    cedula_identidad: str = Field(
        ...,
        min_length=5,
        max_length=20,
        description="Cédula de identidad única",
        examples=["12345678"]
    )
    telefono: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Teléfono del empleado",
        examples=["3001234567"]
    )


class EmpleadoCreate(EmpleadoBase):
    """Esquema para crear un Empleado."""
    puesto_id: int = Field(
        ...,
        gt=0,
        description="ID del puesto asignado",
        examples=[1]
    )
    salario_base: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Salario base mensual del empleado",
        examples=[1500.00]
    )


class EmpleadoUpdate(BaseModel):
    """Esquema para actualizar un Empleado."""
    nombre: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nombre del empleado",
    )
    apellido: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Apellido del empleado",
    )
    telefono: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Teléfono del empleado",
    )
    puesto_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID del puesto asignado",
    )
    salario_base: Optional[Decimal] = Field(
        default=None,
        gt=0,
        decimal_places=2,
        description="Salario base mensual del empleado",
    )
    activo: Optional[bool] = Field(
        default=None,
        description="Estado del empleado (activo/inactivo)",
    )


class EmpleadoResponse(EmpleadoBase):
    """Esquema de respuesta para Empleado."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del empleado"
    )
    puesto_id: int = Field(
        ...,
        description="ID del puesto asignado"
    )
    fecha_ingreso: date = Field(
        ...,
        description="Fecha de ingreso al restaurante"
    )
    salario_base: Decimal = Field(
        ...,
        description="Salario base mensual del empleado"
    )
    activo: bool = Field(
        ...,
        description="Estado del empleado (activo/inactivo)"
    )
    puesto: Optional[PuestoResponse] = Field(
        default=None,
        description="Información del puesto asociado"
    )


# =============================================================================
# Usuario Schemas
# =============================================================================

class UsuarioBase(BaseModel):
    """Esquema base para Usuario."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nombre de usuario único",
        examples=["jperez"]
    )


class UsuarioCreate(UsuarioBase):
    """Esquema para crear un Usuario."""
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Contraseña en texto plano",
        examples=["MiClave123"]
    )
    rol: RolEnum = Field(
        ...,
        description="Rol del usuario en el sistema",
        examples=[RolEnum.VENDEDOR]
    )
    empleado_id: int = Field(
        ...,
        gt=0,
        description="ID del empleado asociado",
        examples=[1]
    )

    @field_validator("password")
    @classmethod
    def validar_longitud_bcrypt(cls, password: str) -> str:
        return validar_password_bcrypt(password)


class UsuarioResponse(UsuarioBase):
    """Esquema de respuesta para Usuario.

    IMPORTANTE: Nunca incluye password ni password_hash.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(
        ...,
        description="ID único del usuario"
    )
    rol: str = Field(
        ...,
        description="Rol del usuario"
    )
    empleado_id: int = Field(
        ...,
        description="ID del empleado asociado"
    )
    activo: bool = Field(
        ...,
        description="Estado del usuario (activo/inactivo)"
    )
    turno_habilitado: bool = Field(
        ...,
        description="Si es Vendedor, indica si puede iniciar turno (habilitado por gerencia)"
    )


class PasswordResetRequest(BaseModel):
    """Esquema para restablecer la contraseña de un usuario."""
    nueva_password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Nueva contraseña temporal",
        examples=["NuevaClave123"]
    )

    @field_validator("nueva_password")
    @classmethod
    def validar_longitud_bcrypt(cls, password: str) -> str:
        return validar_password_bcrypt(password)


class EliminarEmpleadoRequest(BaseModel):
    """Esquema para dar de baja a un empleado.

    Requiere la contraseña del usuario autenticado para autorizar la acción.
    """
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Contraseña del usuario en sesión para autorizar la baja",
        examples=["MiClave123"]
    )


class EliminarUsuarioResponse(BaseModel):
    """Esquema de respuesta al eliminar un usuario del sistema."""
    resultado: str = Field(
        ...,
        description="'eliminado' si se borró físicamente, 'archivado' si se conservó con username renombrado",
        examples=["archivado"]
    )
    mensaje: str = Field(
        ...,
        description="Mensaje legible del resultado de la operación",
        examples=["El usuario 'prueba02' y su empleado fueron eliminados porque no tienen registros contables."]
    )


class TurnoHabilitadoUpdate(BaseModel):
    """Esquema para cambiar la habilitación de turno de un usuario Vendedor."""
    turno_habilitado: bool = Field(
        ...,
        description="True permite al Vendedor iniciar su turno, False lo bloquea"
    )


class TurnoMasivoResponse(BaseModel):
    """Esquema de respuesta para la habilitación masiva de turnos."""
    actualizados: int = Field(
        ...,
        ge=0,
        description="Cantidad de usuarios Vendedor actualizados"
    )
