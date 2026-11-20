"""Reglas de comandas para bebidas.

Una comanda solo de bebidas no tiene nada que cocinar: nace lista para servir
y no debe entrar a la cola de cocina. Una comanda mixta sigue el flujo normal.

Se usa SQLite en memoria; nunca toca la base real.
"""

import unittest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.clasificacion import es_categoria_bebida
from app.core.database import Base
from app.models.menu import CategoriaMenu, MenuItem
from app.models.orden import EstadoOrden, Orden
from app.models.personal import Usuario
from app.schemas.orden import DetalleOrdenCreate, OrdenCreate
from app.schemas.orden import DetalleOrdenResponse
from app.services.orden_service import OrdenService


class BebidasComandaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.usuario = Usuario(
            username="mesero",
            password_hash="hash",
            rol="Vendedor",
            empleado_id=1,
        )
        self.cat_bebidas = CategoriaMenu(nombre="Bebidas")
        self.cat_platos = CategoriaMenu(nombre="Platos Fuertes")
        self.db.add_all([self.usuario, self.cat_bebidas, self.cat_platos])
        self.db.flush()

        self.refresco = MenuItem(
            nombre="Refresco",
            precio=Decimal("45.00"),
            categoria_id=self.cat_bebidas.id,
            disponible=True,
        )
        self.cerveza = MenuItem(
            nombre="Cerveza",
            precio=Decimal("70.00"),
            categoria_id=self.cat_bebidas.id,
            disponible=True,
        )
        self.plato = MenuItem(
            nombre="Arroz con camarón",
            precio=Decimal("350.00"),
            categoria_id=self.cat_platos.id,
            disponible=True,
        )
        self.db.add_all([self.refresco, self.cerveza, self.plato])
        self.db.commit()

        self.service = OrdenService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _crear(self, *productos: MenuItem) -> Orden:
        datos = OrdenCreate(
            mesa_id=None,
            detalles=[
                DetalleOrdenCreate(producto_id=p.id, cantidad=1) for p in productos
            ],
        )
        return self.service.crear_orden(datos, self.usuario.id, self.usuario)

    def test_una_comanda_solo_de_bebidas_nace_lista_para_servir(self) -> None:
        orden = self._crear(self.refresco, self.cerveza)

        self.assertEqual(orden.estado, EstadoOrden.ENTREGADA)

    def test_una_comanda_con_platos_sigue_el_flujo_de_cocina(self) -> None:
        orden = self._crear(self.refresco, self.plato)

        self.assertEqual(orden.estado, EstadoOrden.PENDIENTE)

    def test_una_comanda_solo_de_platos_necesita_cocina(self) -> None:
        orden = self._crear(self.plato)

        self.assertEqual(orden.estado, EstadoOrden.PENDIENTE)

    def test_agregar_solo_bebidas_no_devuelve_la_comanda_a_cocina(self) -> None:
        orden = self._crear(self.refresco)

        actualizada = self.service.agregar_items_canonico(
            orden.id,
            [DetalleOrdenCreate(producto_id=self.cerveza.id, cantidad=2)],
            self.usuario,
        )

        self.assertEqual(actualizada.estado, EstadoOrden.ENTREGADA)

    def test_agregar_un_plato_devuelve_la_comanda_a_cocina(self) -> None:
        orden = self._crear(self.refresco)

        actualizada = self.service.agregar_items_canonico(
            orden.id,
            [DetalleOrdenCreate(producto_id=self.plato.id, cantidad=1)],
            self.usuario,
        )

        self.assertEqual(actualizada.estado, EstadoOrden.PENDIENTE)

    def test_el_detalle_expone_si_es_bebida(self) -> None:
        orden = self._crear(self.refresco, self.plato)
        detalles = {d.producto_id: d for d in orden.detalles}

        refresco = DetalleOrdenResponse.model_validate(detalles[self.refresco.id])
        plato = DetalleOrdenResponse.model_validate(detalles[self.plato.id])

        self.assertTrue(refresco.es_bebida)
        self.assertFalse(plato.es_bebida)


class ClasificacionBebidaTests(unittest.TestCase):
    def test_reconoce_las_categorias_de_bebidas_sin_acentos(self) -> None:
        self.assertTrue(es_categoria_bebida("Bebidas"))
        self.assertTrue(es_categoria_bebida("Cócteles"))
        self.assertTrue(es_categoria_bebida("cocteleria"))
        self.assertTrue(es_categoria_bebida("CERVEZAS"))
        self.assertTrue(es_categoria_bebida("Jugos naturales"))

    def test_no_confunde_platos_con_bebidas(self) -> None:
        self.assertFalse(es_categoria_bebida("Entradas"))
        self.assertFalse(es_categoria_bebida("Platos Fuertes"))
        self.assertFalse(es_categoria_bebida(None))


if __name__ == "__main__":
    unittest.main()
