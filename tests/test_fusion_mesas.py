import unittest
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
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

    def test_cannot_reuse_color_from_another_fusion(self) -> None:
        mesas_adicionales = [
            Mesa(numero=numero, zona_id=self.zona.id, estado=EstadoMesa.LIBRE)
            for numero in (3, 4)
        ]
        self.db.add_all(mesas_adicionales)
        self.db.commit()
        servicio = SalonService(self.db)
        servicio.fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#2A9D8F",
        )

        with self.assertRaises(HTTPException) as error:
            servicio.fusionar_mesas(
                [mesa.id for mesa in mesas_adicionales],
                color="#2a9d8f",
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("ya está siendo utilizado", error.exception.detail)

    def test_existing_fusion_may_keep_its_own_color(self) -> None:
        mesas_adicionales = [
            Mesa(numero=numero, zona_id=self.zona.id, estado=EstadoMesa.LIBRE)
            for numero in (3,)
        ]
        self.db.add_all(mesas_adicionales)
        self.db.commit()
        servicio = SalonService(self.db)
        fusion = servicio.fusionar_mesas(
            [mesa.id for mesa in self.mesas],
            color="#2A9D8F",
        )

        updated = servicio.fusionar_mesas(
            [self.mesas[0].id, mesas_adicionales[0].id],
            color=fusion.color_fusion,
        )

        self.assertEqual(updated.grupo_fusion_id, fusion.grupo_fusion_id)
        self.assertEqual(updated.color_fusion, "#2A9D8F")

    def test_automatic_color_selection_fails_when_palette_is_full(self) -> None:
        from app.services.salon_service import PALETA_FUSION

        grupos = []
        numero = 3
        for color in PALETA_FUSION:
            mesas_grupo = [
                Mesa(numero=numero + offset, zona_id=self.zona.id, estado=EstadoMesa.LIBRE)
                for offset in range(2)
            ]
            numero += 2
            self.db.add_all(mesas_grupo)
            self.db.commit()
            grupos.append(mesas_grupo)
            SalonService(self.db).fusionar_mesas(
                [mesa.id for mesa in mesas_grupo],
                color=color,
            )

        with self.assertRaises(HTTPException) as error:
            SalonService(self.db).fusionar_mesas(
                [mesa.id for mesa in self.mesas],
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("Todos los colores", error.exception.detail)
