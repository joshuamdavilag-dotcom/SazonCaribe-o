from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.database import Base
from app.models.personal import Empleado, Puesto, Usuario
from app.models.importacion_inventario import (
    AccionImportacion,
    EstadoImportacion,
    ImportacionInventario,
)
from app.models.inventario import CategoriaInsumo, Insumo, MovimientoInventario, UnidadMedida
from app.schemas.importacion_inventario import (
    DetalleImportacionAplicar,
    ImportacionAplicarRequest,
)
from app.services.importacion_inventario_parser import (
    extraer_unidad_y_factor,
    normalizar_numero,
    parsear_texto_libre,
)
from app.services.importacion_inventario_service import ImportacionInventarioService


class _GeminiNulo:
    disponible = False


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    for nombre, abreviatura in (
        ("Unidad", "Und"),
        ("Libra", "lb"),
        ("Gramo", "g"),
    ):
        db.add(
            UnidadMedida(
                nombre=nombre,
                abreviatura=abreviatura,
                tipo_magnitud="PESO" if nombre != "Unidad" else "UNIDAD",
                unidad_base_id=None,
                factor_conversion=1.0,
            )
        )
    db.flush()
    db.commit()
    return db


def _actor(db) -> Usuario:
    puesto = Puesto(nombre="Gerente", salario_base=Decimal("20000"))
    db.add(puesto)
    db.flush()
    empleado = Empleado(
        nombre="Ana",
        apellido="López",
        puesto_id=puesto.id,
        salario_base=Decimal("20000"),
    )
    db.add(empleado)
    db.flush()
    usuario = Usuario(
        username="gerente",
        password_hash="x",
        rol="Gerente",
        empleado_id=empleado.id,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _servicio(db) -> ImportacionInventarioService:
    return ImportacionInventarioService(db, gemini=_GeminiNulo())


def _payload(lote) -> ImportacionAplicarRequest:
    return ImportacionAplicarRequest(
        detalles=[
            DetalleImportacionAplicar(
                id=detalle.id,
                accion=detalle.accion,
                nombre=detalle.nombre_detectado,
                cantidad=detalle.cantidad,
                unidad_medida_id=detalle.unidad_medida_id,
                unidad_empaque_id=detalle.unidad_empaque_id,
                unidad_empaque_nombre=detalle.unidad_texto,
                factor_empaque=detalle.factor_empaque,
                precio_unitario=detalle.precio_unitario,
                precio_total=detalle.precio_total,
                categoria_id=detalle.categoria_id,
                categoria_nombre=detalle.categoria_texto,
                stock_minimo=detalle.stock_minimo,
            )
            for detalle in lote.detalles
        ]
    )


def test_normalizar_numero_acepta_formatos_mixtos():
    assert normalizar_numero("C$1,234.56") == Decimal("1234.56")
    assert normalizar_numero("1.234,56") == Decimal("1234.56")
    assert normalizar_numero("12,5") == Decimal("12.5")
    assert normalizar_numero("  2 480 ") == Decimal("2480")
    assert normalizar_numero("") is None


def test_extraer_unidad_y_factor_distingue_empaques():
    assert extraer_unidad_y_factor("cajilla de coca colas x24") == ("Cajilla", 24.0, None)
    assert extraer_unidad_y_factor("saco de 100 libras") == ("Saco", 100.0, "Libra")
    assert extraer_unidad_y_factor("libra")[:2] == ("Libra", None)


def test_parsear_texto_libre_reconoce_producto_cantidad_precio():
    filas = parsear_texto_libre("Coca Cola | 2 | 480\nArroz libra 5 20")
    assert [f.nombre for f in filas] == ["Coca Cola", "Arroz"]
    assert filas[0].cantidad == Decimal("2.00")
    assert filas[0].precio_unitario == Decimal("480.00")
    assert filas[1].unidad_texto == "Libra"


def test_analizar_y_aplicar_con_empaques_por_producto():
    db = _session()
    try:
        actor = _actor(db)
        servicio = _servicio(db)
        contenido = (
            "Producto | Cantidad | Unidad | Precio\n"
            "Coca Cola | 2 | cajilla x24 | 480\n"
            "Huevos | 1 | cajilla x30 | 300\n"
            "Arroz | 5 | libra | 20\n"
        ).encode("utf-8")

        lote = servicio.analizar("compra.txt", contenido, actor)
        assert lote.estado == EstadoImportacion.REVISION
        assert len(lote.detalles) == 3
        assert lote.resumen["crear"] == 3
        assert lote.resumen["empaques_nuevos"] == ["Cajilla"]

        resultado = servicio.aplicar(lote.id, _payload(lote), actor)
        assert resultado.creadas == 3
        assert resultado.actualizadas == 0
        assert resultado.total_movimientos == 3

        coca = db.execute(
            select(Insumo).where(Insumo.nombre == "Coca Cola")
        ).scalar_one()
        huevos = db.execute(select(Insumo).where(Insumo.nombre == "Huevos")).scalar_one()
        arroz = db.execute(select(Insumo).where(Insumo.nombre == "Arroz")).scalar_one()

        assert coca.cantidad_actual == Decimal("48.00")
        assert coca.costo_unitario == Decimal("20.00")
        assert coca.factor_empaque == 24.0
        assert huevos.cantidad_actual == Decimal("30.00")
        assert huevos.costo_unitario == Decimal("10.00")
        assert huevos.factor_empaque == 30.0
        assert coca.unidad_empaque_id == huevos.unidad_empaque_id
        assert arroz.cantidad_actual == Decimal("5.00")
        assert arroz.costo_unitario == Decimal("20.00")

        movimientos = db.execute(select(MovimientoInventario)).scalars().all()
        assert len(movimientos) == 3
        assert all(movimiento.tipo == "ENTRADA" for movimiento in movimientos)

        lote_modelo = db.get(ImportacionInventario, lote.id)
        assert lote_modelo.estado == EstadoImportacion.APLICADA
        assert lote_modelo.aplicada_en is not None
        assert lote_modelo.resumen["movimientos"] == 3

        with pytest.raises(HTTPException) as error:
            servicio.aplicar(lote.id, _payload(lote), actor)
        assert error.value.status_code == 400
    finally:
        db.close()


def test_actualizar_insumo_existente_suma_stock_y_mantiene_unidad():
    db = _session()
    try:
        actor = _actor(db)
        unidad = db.execute(
            select(UnidadMedida).where(UnidadMedida.nombre == "Libra")
        ).scalar_one()
        existente = Insumo(
            nombre="Arroz",
            cantidad_actual=Decimal("10.00"),
            unidad_medida_id=unidad.id,
            stock_minimo=Decimal("2.00"),
            costo_unitario=Decimal("18.00"),
        )
        db.add(existente)
        db.commit()

        servicio = _servicio(db)
        lote = servicio.analizar(
            "inventario.csv",
            "Producto,Cantidad,Precio\narroz,5,20\n".encode("utf-8"),
            actor,
        )
        detalle = lote.detalles[0]
        assert detalle.accion == AccionImportacion.ACTUALIZAR
        assert detalle.insumo_id == existente.id

        payload = ImportacionAplicarRequest(
            detalles=[
                DetalleImportacionAplicar(
                    id=detalle.id,
                    accion="ACTUALIZAR",
                    nombre="Arroz",
                    cantidad=Decimal("5"),
                    precio_unitario=Decimal("20"),
                    stock_minimo=Decimal("3"),
                    categoria_nombre="Granos",
                )
            ]
        )
        resultado = servicio.aplicar(lote.id, payload, actor)
        assert resultado.actualizadas == 1
        assert resultado.creadas == 0

        db.refresh(existente)
        assert existente.cantidad_actual == Decimal("15.00")
        assert existente.costo_unitario == Decimal("20.00")
        assert existente.stock_minimo == Decimal("3.00")
        assert existente.categoria_id is not None
        categoria = db.get(CategoriaInsumo, existente.categoria_id)
        assert categoria.nombre == "Granos"
    finally:
        db.close()


def test_coincidencia_aproximada_no_actualiza_insumo_ni_reutiliza_categoria():
    db = _session()
    try:
        actor = _actor(db)
        unidad = db.execute(
            select(UnidadMedida).where(UnidadMedida.nombre == "Unidad")
        ).scalar_one()
        categoria = CategoriaInsumo(nombre="Bebidas")
        existente = Insumo(
            nombre="Coca Cola",
            cantidad_actual=Decimal("4.00"),
            unidad_medida_id=unidad.id,
            stock_minimo=Decimal("2.00"),
            categoria=categoria,
        )
        db.add_all([categoria, existente])
        db.commit()

        servicio = _servicio(db)
        lote = servicio.analizar(
            "compra.txt",
            "Producto | Cantidad | Unidad | Categoría | Precio\n"
            "Coca Colas | 2 | unidad | Bebida | 30\n".encode("utf-8"),
            actor,
        )
        detalle = lote.detalles[0]
        assert detalle.accion == AccionImportacion.CREAR
        assert detalle.insumo_id == existente.id
        assert detalle.categoria_id is None
        assert "Posible coincidencia" in detalle.notas

        resultado = servicio.aplicar(lote.id, _payload(lote), actor)
        assert resultado.creadas == 1
        db.refresh(existente)
        assert existente.cantidad_actual == Decimal("4.00")
        assert db.execute(
            select(CategoriaInsumo).where(CategoriaInsumo.nombre == "Bebida")
        ).scalar_one()
        assert db.execute(
            select(Insumo).where(Insumo.nombre == "Coca Colas")
        ).scalar_one()
    finally:
        db.close()


def test_aplicar_omite_filas_marcadas_y_no_escribe_nada_si_falla():
    db = _session()
    try:
        actor = _actor(db)
        servicio = _servicio(db)
        lote = servicio.analizar(
            "lista.txt", "Sal | 2 | 10\nAzúcar | 3 | 15\n".encode("utf-8"), actor
        )

        detalle_sal, detalle_azucar = lote.detalles
        payload = ImportacionAplicarRequest(
            detalles=[
                DetalleImportacionAplicar(
                    id=detalle_sal.id,
                    accion="OMITIR",
                    nombre=detalle_sal.nombre_detectado,
                    cantidad=detalle_sal.cantidad,
                ),
                DetalleImportacionAplicar(
                    id=detalle_azucar.id,
                    accion="CREAR",
                    nombre=detalle_azucar.nombre_detectado,
                    cantidad=detalle_azucar.cantidad,
                    categoria_id=9999,
                ),
            ]
        )
        with pytest.raises(HTTPException) as error:
            servicio.aplicar(lote.id, payload, actor)
        assert error.value.status_code == 400

        db.rollback()
        assert db.execute(select(Insumo)).scalars().all() == []
        lote_recargado = db.get(ImportacionInventario, lote.id)
        assert lote_recargado.estado == EstadoImportacion.REVISION
        assert db.execute(select(MovimientoInventario)).scalars().all() == []
    finally:
        db.close()


def test_no_se_puede_eliminar_una_importacion_aplicada():
    db = _session()
    try:
        actor = _actor(db)
        servicio = _servicio(db)
        lote = servicio.analizar("uno.txt", "Leche | 4 | 25\n".encode("utf-8"), actor)
        servicio.aplicar(lote.id, _payload(lote), actor)

        with pytest.raises(HTTPException) as error:
            servicio.eliminar(lote.id)
        assert error.value.status_code == 400
    finally:
        db.close()


def test_fila_omitida_acepta_nombre_vacio_y_activa_lo_exige():
    db = _session()
    try:
        actor = _actor(db)
        servicio = _servicio(db)
        lote = servicio.analizar(
            "lista.txt", "Sal | 2 | 10\nAzúcar | 3 | 15\n".encode("utf-8"), actor
        )
        detalle_sal, detalle_azucar = lote.detalles

        sin_nombre = DetalleImportacionAplicar(
            id=detalle_sal.id,
            accion="OMITIR",
            cantidad=detalle_sal.cantidad,
        )
        assert sin_nombre.nombre == ""

        omitida = servicio.aplicar(
            lote.id,
            ImportacionAplicarRequest(
                detalles=[
                    sin_nombre,
                    DetalleImportacionAplicar(
                        id=detalle_azucar.id,
                        accion="OMITIR",
                        cantidad=detalle_azucar.cantidad,
                    ),
                ]
            ),
            actor,
        )
        assert omitida.omitidas == 2
        assert omitida.creadas == 0

        lote2 = servicio.analizar("otra.txt", "Canela | 1 | 30\n".encode("utf-8"), actor)
        detalle = lote2.detalles[0]
        with pytest.raises(HTTPException) as error:
            servicio.aplicar(
                lote2.id,
                ImportacionAplicarRequest(
                    detalles=[
                        DetalleImportacionAplicar(
                            id=detalle.id,
                            accion="CREAR",
                            cantidad=detalle.cantidad,
                        )
                    ]
                ),
                actor,
            )
        assert error.value.status_code == 400
        assert "nombre" in error.value.detail.lower()
    finally:
        db.close()
