"""Consultas de órdenes: filtros de rendimiento (solo activas y límite)."""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.models.menu import CategoriaMenu, MenuItem
from app.models.orden import DetalleOrden, EstadoOrden, Orden
from app.models.personal import Empleado, Puesto, Usuario
from app.repositories.orden_repository import OrdenRepository


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _sembrar(db):
    puesto = Puesto(nombre="Mesero", salario_base=Decimal("6000.00"))
    db.add(puesto)
    db.flush()
    empleado = Empleado(
        cedula_identidad="000-000000-0000A",
        nombre="Ana",
        apellido="Lopez",
        puesto_id=puesto.id,
        fecha_ingreso=datetime(2026, 1, 1).date(),
        salario_base=Decimal("6000.00"),
    )
    db.add(empleado)
    db.flush()
    usuario = Usuario(
        username="ana",
        password_hash="x",
        rol="Vendedor",
        empleado_id=empleado.id,
        turno_habilitado=True,
    )
    db.add(usuario)
    categoria = CategoriaMenu(nombre="Platos", descripcion="t")
    db.add(categoria)
    db.flush()
    plato = MenuItem(
        nombre="Sopa",
        precio=Decimal("100.00"),
        disponible=True,
        categoria_id=categoria.id,
    )
    db.add(plato)
    db.flush()

    estados = [
        EstadoOrden.PENDIENTE,
        EstadoOrden.PREPARANDO,
        EstadoOrden.ENTREGADA,
        EstadoOrden.PAGADA,
        EstadoOrden.CANCELADA,
    ]
    for i, estado in enumerate(estados):
        orden = Orden(
            mesa_id=None,
            mesero_id=empleado.id,
            estado=estado,
            subtotal=Decimal("100.00"),
            descuento_total=Decimal("0.00"),
            total=Decimal("100.00"),
            fecha_creacion=datetime.now() + timedelta(minutes=i),
        )
        db.add(orden)
        db.flush()
        db.add(DetalleOrden(
            orden_id=orden.id,
            producto_id=plato.id,
            cantidad=1,
            precio_unitario=Decimal("100.00"),
        ))
    db.commit()
    return empleado


def test_solo_activas_excluye_historico():
    db = _session()
    try:
        _sembrar(db)
        activas = OrdenRepository(db).obtener_ordenes_filtradas(solo_activas=True)
        estados = {o.estado for o in activas}
        assert len(activas) == 3
        assert estados == {
            EstadoOrden.PENDIENTE,
            EstadoOrden.PREPARANDO,
            EstadoOrden.ENTREGADA,
        }
    finally:
        db.close()


def test_limite_devuelve_las_mas_recientes():
    db = _session()
    try:
        _sembrar(db)
        repo = OrdenRepository(db)
        todas = repo.obtener_ordenes_filtradas()
        dos = repo.obtener_ordenes_filtradas(limite=2)
        assert len(todas) == 5
        assert len(dos) == 2
        assert [o.id for o in dos] == [o.id for o in todas[:2]]
    finally:
        db.close()


def test_filtro_por_mesa_y_estado_siguen_funcionando():
    db = _session()
    try:
        _sembrar(db)
        repo = OrdenRepository(db)
        pagadas = repo.obtener_ordenes_filtradas(estado=EstadoOrden.PAGADA)
        assert len(pagadas) == 1
        assert pagadas[0].estado == EstadoOrden.PAGADA
        assert repo.obtener_ordenes_filtradas(mesa_id=999) == []
    finally:
        db.close()
