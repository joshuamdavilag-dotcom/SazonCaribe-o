import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.menu import MenuItem
from app.models.orden import EstadoOrden, MetodoPago, Orden
from app.models.personal import Usuario
from app.models.salon import EstadoMesa, Mesa, Zona
from app.schemas.orden import DetalleOrdenCreate, OrdenCreate
from app.services.orden_service import OrdenService
from app.services.pago_comanda_service import PagoComandaService
from app.services.salon_service import SalonService


class MultiComandaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.zona = Zona(nombre="Salón")
        self.db.add(self.zona)
        self.db.flush()
        self.mesas = [
            Mesa(numero=numero, zona_id=self.zona.id, estado=EstadoMesa.LIBRE)
            for numero in (1, 2)
        ]
        self.usuario = Usuario(
            username="mesero",
            password_hash="hash",
            rol="Vendedor",
            empleado_id=1,
        )
        self.producto = MenuItem(
            nombre="Plato de prueba",
            precio=Decimal("5.00"),
            categoria_id=1,
        )
        self.db.add_all([*self.mesas, self.usuario, self.producto])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _crear_comanda(self, mesa_id: int) -> Orden:
        return OrdenService(self.db).crear_orden(
            OrdenCreate(
                mesa_id=mesa_id,
                detalles=[
                    DetalleOrdenCreate(producto_id=self.producto.id, cantidad=1)
                ],
            ),
            mesero_id=self.usuario.id,
            actor=self.usuario,
        )

    def _cobrar(self, orden: Orden) -> None:
        PagoComandaService(self.db).registrar_pago(
            orden_id=orden.id,
            metodo_pago=MetodoPago.EFECTIVO,
            usuario=self.usuario,
            monto=orden.total,
        )

    def test_two_comandas_can_share_one_occupied_table(self) -> None:
        primera = self._crear_comanda(self.mesas[0].id)
        segunda = self._crear_comanda(self.mesas[0].id)

        self.db.refresh(self.mesas[0])
        self.assertNotEqual(primera.id, segunda.id)
        self.assertEqual(self.mesas[0].estado, EstadoMesa.OCUPADA)
        activas = (
            self.db.query(Orden)
            .filter(
                Orden.mesa_id == self.mesas[0].id,
                Orden.estado == EstadoOrden.PENDIENTE,
            )
            .all()
        )
        self.assertEqual(len(activas), 2)

    def test_table_is_freed_only_after_paying_the_last_comanda(self) -> None:
        primera = self._crear_comanda(self.mesas[0].id)
        segunda = self._crear_comanda(self.mesas[0].id)

        self._cobrar(primera)
        self.db.refresh(self.mesas[0])
        self.assertEqual(self.mesas[0].estado, EstadoMesa.OCUPADA)

        self._cobrar(segunda)
        self.db.refresh(self.mesas[0])
        self.assertEqual(self.mesas[0].estado, EstadoMesa.LIBRE)

    def test_fusion_accepts_multiple_comandas_and_dissolves_after_last_payment(self) -> None:
        fusion = SalonService(self.db).fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#006b33",
        )
        principal_id = fusion.mesa_principal_id
        miembro_id = next(mesa.id for mesa in self.mesas if mesa.id != principal_id)

        primera = self._crear_comanda(principal_id)
        segunda = self._crear_comanda(miembro_id)

        self.assertEqual(segunda.mesa_id, principal_id)
        grupo = SalonService(self.db).salon_repo.obtener_mesas_por_grupo(
            fusion.grupo_fusion_id
        )
        self.assertTrue(all(mesa.estado == EstadoMesa.OCUPADA for mesa in grupo))

        self._cobrar(primera)
        grupo = SalonService(self.db).salon_repo.obtener_mesas_por_grupo(
            fusion.grupo_fusion_id
        )
        self.assertTrue(
            all(mesa.grupo_fusion_id == fusion.grupo_fusion_id for mesa in grupo)
        )
        self.assertTrue(all(mesa.estado == EstadoMesa.OCUPADA for mesa in grupo))

        self._cobrar(segunda)
        mesas = (
            self.db.query(Mesa)
            .filter(Mesa.id.in_([mesa.id for mesa in self.mesas]))
            .all()
        )
        self.assertTrue(all(mesa.grupo_fusion_id is None for mesa in mesas))
        self.assertTrue(all(mesa.estado == EstadoMesa.LIBRE for mesa in mesas))


    def test_separating_principal_moves_every_comanda_to_new_principal(self) -> None:
        fusion = SalonService(self.db).fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#006b33",
        )
        principal_id = fusion.mesa_principal_id
        primera = self._crear_comanda(principal_id)
        segunda = self._crear_comanda(principal_id)

        response = SalonService(self.db).separar_mesa(principal_id)

        nuevo_principal = response.mesa_principal_id
        self.assertIsNotNone(nuevo_principal)
        self.assertNotEqual(nuevo_principal, principal_id)
        for orden in (primera, segunda):
            self.db.refresh(orden)
            self.assertEqual(orden.mesa_id, nuevo_principal)
        self.assertEqual(
            self.db.get(Mesa, principal_id).estado,
            EstadoMesa.LIBRE,
        )
        self.assertEqual(
            self.db.get(Mesa, nuevo_principal).estado,
            EstadoMesa.OCUPADA,
        )


if __name__ == "__main__":
    unittest.main()
