import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
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
