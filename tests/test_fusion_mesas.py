import unittest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.orden import EstadoOrden, Orden
from app.models.personal import Usuario
from app.models.salon import EstadoMesa, Mesa, Zona
from app.services.salon_service import SalonService


class FusionMesasTests(unittest.TestCase):
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
        self.db.add_all(self.mesas)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_fusion_without_active_order_keeps_tables_free(self) -> None:
        response = SalonService(self.db).fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#2A9D8F",
        )

        self.assertIsNone(response.orden_id)
        self.assertEqual(len(response.mesas), 2)
        self.assertEqual(
            {mesa.grupo_fusion_id for mesa in response.mesas},
            {response.grupo_fusion_id},
        )
        self.assertTrue(all(mesa.estado == EstadoMesa.LIBRE for mesa in response.mesas))

    def test_removing_fusion_keeps_active_order_open_at_its_table(self) -> None:
        SalonService(self.db).fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#2A9D8F",
        )
        usuario = Usuario(
            username="mesero",
            password_hash="hash",
            rol="Vendedor",
            empleado_id=1,
        )
        self.db.add(usuario)
        self.db.flush()
        orden = Orden(
            mesa_id=self.mesas[0].id,
            mesero_id=usuario.id,
            estado=EstadoOrden.PENDIENTE,
            total=Decimal("10.00"),
            subtotal=Decimal("10.00"),
            descuento_total=Decimal("0.00"),
            fecha_creacion=datetime.now(),
        )
        self.db.add(orden)
        self.mesas[0].estado = EstadoMesa.OCUPADA
        self.db.commit()

        response = SalonService(self.db).deshacer_fusion(self.mesas[0].id)

        self.db.refresh(orden)
        self.assertEqual(response.orden_id, orden.id)
        self.assertEqual(orden.estado, EstadoOrden.PENDIENTE)
        self.assertEqual(orden.mesa_id, self.mesas[0].id)
        self.assertEqual(self.mesas[0].estado, EstadoMesa.OCUPADA)
        self.assertEqual(self.mesas[1].estado, EstadoMesa.LIBRE)
        self.assertTrue(all(mesa.grupo_fusion_id is None for mesa in response.mesas))
