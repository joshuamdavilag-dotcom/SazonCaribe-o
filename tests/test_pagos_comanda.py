import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.menu import MenuItem
from app.models.orden import DetalleOrden, EstadoOrden, MetodoPago, Orden
from app.models.pago_comanda import PagoComanda
from app.models.personal import Usuario
from app.models.auditoria import RegistroAuditoria
from app.repositories.estudio_mercado_repository import EstudioMercadoRepository
from app.services.orden_service import OrdenService
from app.services.pago_comanda_service import PagoComandaService
from app.services.salon_service import SalonService


class PagoComandaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.usuario = Usuario(
            username="cajero",
            password_hash="hash",
            rol="Administrador",
            empleado_id=1,
        )
        self.producto = MenuItem(
            nombre="Plato de prueba",
            precio=Decimal("2.00"),
            categoria_id=1,
        )
        self.db.add_all([self.usuario, self.producto])
        self.db.flush()
        self.orden = Orden(
            mesero_id=self.usuario.id,
            mesa_id=9,
            estado=EstadoOrden.ENTREGADA,
            total=Decimal("10.00"),
            subtotal=Decimal("10.00"),
            descuento_total=Decimal("0.00"),
            fecha_creacion=datetime.now(),
        )
        self.orden.detalles.append(DetalleOrden(
            producto_id=self.producto.id,
            cantidad=5,
            precio_unitario=Decimal("2.00"),
            descuento_monto=Decimal("0.00"),
            cantidad_devuelta=0,
        ))
        self.db.add(self.orden)
        self.db.commit()
        self.detalle_id = self.orden.detalles[0].id

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_multiple_payments_keep_order_open_until_balance_is_zero(self) -> None:
        service = PagoComandaService(self.db)

        partial = service.registrar_pago(
            orden_id=self.orden.id,
            metodo_pago=MetodoPago.EFECTIVO,
            usuario=self.usuario,
            monto=Decimal("3.00"),
        )
        self.assertEqual(partial["saldo_pendiente"], Decimal("7.00"))
        self.assertFalse(partial["completada"])

        complete = service.registrar_pago(
            orden_id=self.orden.id,
            metodo_pago=MetodoPago.TARJETA,
            usuario=self.usuario,
            monto=Decimal("7.00"),
        )

        self.db.refresh(self.orden)
        self.assertTrue(complete["completada"])
        self.assertEqual(self.orden.estado, EstadoOrden.PAGADA)
        self.assertEqual(
            [p["metodo_pago"] for p in complete["pagos"]],
            [MetodoPago.EFECTIVO, MetodoPago.TARJETA],
        )
        self.assertTrue(all(p["usuario_id"] == self.usuario.id for p in complete["pagos"]))
        folios = [p["folio_factura"] for p in complete["pagos"]]
        self.assertEqual(len(folios), len(set(folios)))
        self.assertTrue(all(folio.startswith("FC-") and len(folio) == 23 for folio in folios))
        resumen = service.estado_pagos(self.orden.id)
        self.assertEqual(
            [p["folio_factura"] for p in resumen["pagos"]],
            folios,
        )

    def test_item_quantity_is_split_across_people_and_each_part_is_paid_once(self) -> None:
        service = PagoComandaService(self.db)
        quote = service.cotizar_division(
            self.orden.id,
            self.detalle_id,
            cantidad=5,
            personas=2,
        )
        self.assertEqual(
            [(part["cantidad"], part["monto"]) for part in quote["partes"]],
            [(3, Decimal("6.00")), (2, Decimal("4.00"))],
        )

        first_part = service.registrar_pago(
            orden_id=self.orden.id,
            metodo_pago=MetodoPago.EFECTIVO,
            usuario=self.usuario,
            detalle_id=self.detalle_id,
            cantidad=5,
            personas=2,
            parte=1,
        )
        division_id = first_part["pagos"][0]["division_id"]
        self.assertEqual(first_part["saldo_pendiente"], Decimal("4.00"))
        self.assertTrue(first_part["divisiones"][0]["partes"][0]["pagada"])
        self.assertFalse(first_part["divisiones"][0]["partes"][1]["pagada"])

        with self.assertRaises(HTTPException) as raised:
            service.registrar_pago(
                orden_id=self.orden.id,
                metodo_pago=MetodoPago.EFECTIVO,
                usuario=self.usuario,
                division_id=division_id,
                parte=1,
            )
        self.assertEqual(raised.exception.status_code, 409)

        with patch.object(SalonService, "liberar_mesa_si_sin_comandas") as liberar:
            complete = service.registrar_pago(
                orden_id=self.orden.id,
                metodo_pago=MetodoPago.TRANSFERENCIA,
                usuario=self.usuario,
                division_id=division_id,
                parte=2,
            )

        self.assertTrue(complete["completada"])
        liberar.assert_called_once_with(self.orden.mesa_id)

    def test_payment_cannot_exceed_balance(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            PagoComandaService(self.db).registrar_pago(
                orden_id=self.orden.id,
                metodo_pago=MetodoPago.EFECTIVO,
                usuario=self.usuario,
                monto=Decimal("10.01"),
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_canceling_partially_paid_order_registers_refund(self) -> None:
        self.db.add(PagoComanda(
            orden_id=self.orden.id,
            usuario_id=self.usuario.id,
            metodo_pago=MetodoPago.EFECTIVO,
            monto=Decimal("3.00"),
        ))
        self.db.commit()

        canceled = OrdenService(self.db).cambiar_estado(
            self.orden.id,
            EstadoOrden.CANCELADA,
            self.usuario,
        )

        pagos = self.db.query(PagoComanda).filter_by(orden_id=self.orden.id).all()
        self.assertEqual(canceled.estado, EstadoOrden.CANCELADA)
        self.assertEqual(sum((pago.monto for pago in pagos), Decimal("0.00")), Decimal("0.00"))
        self.assertEqual(
            [pago.monto for pago in pagos if pago.usuario_id == self.usuario.id],
            [Decimal("3.00"), Decimal("-3.00")],
        )
        auditoria = self.db.query(RegistroAuditoria).filter_by(
            accion="COMANDA_CANCELADA",
            entidad_id=self.orden.id,
        ).one()
        self.assertEqual(auditoria.despues["monto_reembolsado"], "3.00")

    def test_canceling_unpaid_order_still_succeeds(self) -> None:
        canceled = OrdenService(self.db).cambiar_estado(
            self.orden.id,
            EstadoOrden.CANCELADA,
            self.usuario,
        )

        self.assertEqual(canceled.estado, EstadoOrden.CANCELADA)
        auditoria = self.db.query(RegistroAuditoria).filter_by(
            accion="COMANDA_CANCELADA",
            entidad_id=self.orden.id,
        ).one()
        self.assertEqual(auditoria.despues["monto_reembolsado"], "0.00")

    def test_market_study_sums_mixed_methods_and_keeps_legacy_orders(self) -> None:
        self.orden.estado = EstadoOrden.PAGADA
        self.orden.total = Decimal("10.00")
        self.orden.metodo_pago = MetodoPago.TARJETA
        historica = Orden(
            mesero_id=self.usuario.id,
            estado=EstadoOrden.PAGADA,
            total=Decimal("5.00"),
            subtotal=Decimal("5.00"),
            descuento_total=Decimal("0.00"),
            metodo_pago=MetodoPago.TARJETA,
            fecha_creacion=datetime.now(),
            anulada=False,
        )
        self.db.add(historica)
        self.db.add_all([
            PagoComanda(
                orden_id=self.orden.id,
                usuario_id=self.usuario.id,
                metodo_pago=MetodoPago.EFECTIVO,
                monto=Decimal("3.00"),
            ),
            PagoComanda(
                orden_id=self.orden.id,
                usuario_id=self.usuario.id,
                metodo_pago=MetodoPago.TARJETA,
                monto=Decimal("7.00"),
            ),
        ])
        self.db.commit()

        metodos = EstudioMercadoRepository(self.db).metodos_pago(
            date.today(), date.today()
        )

        self.assertEqual(
            {item["metodo"]: (item["ordenes"], item["monto"]) for item in metodos},
            {
                "EFECTIVO": (1, 3.0),
                "TARJETA": (2, 12.0),
            },
        )


if __name__ == "__main__":
    unittest.main()
