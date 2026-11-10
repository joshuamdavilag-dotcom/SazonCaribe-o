from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Date, Boolean, ForeignKey, Numeric, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Puesto(Base):
    """Modelo de puestos laborales del restaurante."""

    __tablename__ = "puestos"
    __table_args__ = (
        CheckConstraint(
            "salario_base >= 0",
            name="ck_puestos_salario_positivo"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )
    salario_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    # Relación uno-a-muchos con Empleado (carga diferida: con selectin cada
    # lectura de un Puesto traía todos los empleados del puesto).
    empleados: Mapped[List["Empleado"]] = relationship(
        "Empleado",
        back_populates="puesto",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Puesto(id={self.id}, nombre='{self.nombre}', salario={self.salario_base})>"


class Empleado(Base):
    """Modelo de empleados del restaurante."""

    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    apellido: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    cedula_identidad: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )
    telefono: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(254),
        nullable=True
    )
    puesto_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("puestos.id", name="fk_empleados_puesto_id"),
        nullable=False
    )
    fecha_ingreso: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today
    )
    fecha_baja: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    salario_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0")
    )
    salario_base_al_baja: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Relación muchos-a-uno con Puesto
    puesto: Mapped["Puesto"] = relationship(
        "Puesto",
        back_populates="empleados",
        lazy="selectin"
    )

    # Relación uno-a-uno con Usuario (carga diferida: se navega desde Usuario,
    # no desde Empleado, y con selectin generaba una consulta extra por carga).
    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        back_populates="empleado",
        uselist=False,
        lazy="select",
        cascade="all, delete-orphan"
    )

    # Colecciones de historial: carga diferida a propósito. Con lazy="selectin"
    # cada lectura de un Empleado (y de un Usuario, por la cadena Usuario →
    # Empleado) disparaba consultas extra del historial completo de
    # asistencias, nóminas y adelantos en TODAS las peticiones.
    asistencias: Mapped[List["Asistencia"]] = relationship(
        "Asistencia",
        back_populates="empleado",
        lazy="select"
    )

    nominas: Mapped[List["Nomina"]] = relationship(
        "Nomina",
        back_populates="empleado",
        lazy="select"
    )
    adelantos: Mapped[List["AdelantoSalario"]] = relationship(
        "AdelantoSalario",
        back_populates="empleado",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Empleado(id={self.id}, nombre='{self.nombre} {self.apellido}')>"


class Usuario(Base):
    """Modelo de usuarios del sistema."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "rol IN ('Administrador', 'Gerente', 'Vendedor')",
            name="ck_usuarios_rol_valido"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    rol: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    empleado_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleados.id", name="fk_usuarios_empleado_id"),
        unique=True,
        nullable=False
    )
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    turno_habilitado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    avisos_fuera_de_turno: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    avisos_cocina: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    avisos_mesero: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    avisos_mesero_todas: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    permisos: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Overrides de permisos por usuario: {clave: true/false}"
    )

    # Relación uno-a-uno con Empleado
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        back_populates="usuario",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}', rol='{self.rol}')>"
