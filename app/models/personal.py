from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Integer, Date, Boolean, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Puesto(Base):
    """Modelo de puestos laborales del restaurante."""

    __tablename__ = "puestos"
    __table_args__ = (
        CheckConstraint(
            "salario_base > 0",
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

    # Relación uno-a-muchos con Empleado
    empleados: Mapped[List["Empleado"]] = relationship(
        "Empleado",
        back_populates="puesto",
        lazy="selectin"
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
    cedula_identidad: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False
    )
    telefono: Mapped[Optional[str]] = mapped_column(
        String(20),
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
    salario_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0")
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

    # Relación uno-a-uno con Usuario
    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        back_populates="empleado",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    # Relación uno-a-muchos con Asistencia
    asistencias: Mapped[List["Asistencia"]] = relationship(
        "Asistencia",
        back_populates="empleado",
        lazy="selectin"
    )

    # Relación uno-a-muchos con Nomina
    nominas: Mapped[List["Nomina"]] = relationship(
        "Nomina",
        back_populates="empleado",
        lazy="selectin"
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

    # Relación uno-a-uno con Empleado
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        back_populates="usuario",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}', rol='{self.rol}')>"
