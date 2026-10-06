from datetime import date, datetime, time
from decimal import Decimal
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.endpoints.calendario import _validar_rango
from app.core.database import Base
from app.models.asistencia import Asistencia, Turno
from app.models.calendario import EstadoEventoCalendario, TipoEventoCalendario
from app.models.inventario import Insumo, Proveedor, UnidadMedida
from app.models.menu import CategoriaMenu, MenuItem
from app.models.personal import Empleado, Puesto, Usuario
from app.schemas.calendario import CalendarioResponse, EventoCalendarioRequest
from app.services.calendario_service import CalendarioService
from app.services.personal_service import PersonalService


class CalendarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        puesto = Puesto(nombre="Cocinero", salario_base=Decimal("1000.00"))
        self.db.add(puesto)
        self.db.flush()
        empleado = Empleado(
            nombre="Ana",
            apellido="Caribe",
            cedula_identidad="CAL-001",
            puesto_id=puesto.id,
            fecha_ingreso=date(2025, 1, 1),
            salario_base=Decimal("1000.00"),
        )
        self.db.add(empleado)
        self.db.flush()
        self.usuario = Usuario(
            username="calendar_admin",
            password_hash="test",
            rol="Administrador",
            empleado_id=empleado.id,
            activo=True,
            turno_habilitado=True,
        )
        turno = Turno(
            nombre="Matutino",
            hora_entrada=time(8, 0),
            hora_salida=time(16, 0),
            horas_teoricas=8,
        )
        categoria = CategoriaMenu(nombre="Platos")
        unidad = UnidadMedida(nombre="Unidad", abreviatura="u")
        proveedor = Proveedor(nombre="Distribuidora Caribe")
        self.db.add_all([self.usuario, turno, categoria, unidad, proveedor])
        self.db.flush()
        self.platillo = MenuItem(
            nombre="Pescado caribeño",
            precio=Decimal("250.00"),
            categoria_id=categoria.id,
            disponible=True,
        )
        self.insumo = Insumo(
            nombre="Pescado",
            cantidad_actual=Decimal("10.00"),
            unidad_medida_id=unidad.id,
            stock_minimo=Decimal("1.00"),
            costo_unitario=Decimal("50.00"),
        )
        self.db.add_all([self.platillo, self.insumo])
        self.db.flush()
        self.proveedor = proveedor
        self.turno = turno
        self.empleado = empleado
        self.db.add_all([
            Asistencia(
                empleado_id=empleado.id,
                turno_id=turno.id,
                fecha=date(2026, 5, 12),
                hora_entrada_real=datetime(2026, 5, 12, 8, 0),
                anulada=False,
            ),
            Asistencia(
                empleado_id=empleado.id,
                turno_id=turno.id,
                fecha=date(2026, 5, 12),
                hora_entrada_real=datetime(2026, 5, 12, 9, 0),
                anulada=True,
            ),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_plan_event_and_real_attendance_are_returned_without_annulled_rows(self) -> None:
        datos = EventoCalendarioRequest(
            tipo=TipoEventoCalendario.DISPONIBILIDAD_PLATILLO,
            titulo="Disponible para almuerzo",
            fecha_inicio=date(2026, 5, 12),
            hora_inicio=time(11, 0),
            hora_fin=time(15, 0),
            menu_item_id=self.platillo.id,
        )
        created = CalendarioService(self.db).crear_evento(datos, self.usuario.id)

        result = CalendarioService(self.db).obtener_calendario(
            date(2026, 5, 12),
            date(2026, 5, 12),
        )
        response = CalendarioResponse.model_validate(result)

        self.assertEqual(len(response.eventos), 1)
        self.assertEqual(response.eventos[0].id, created.id)
        self.assertEqual(response.eventos[0].menu_item_nombre, "Pescado caribeño")
        self.assertTrue(PersonalService(self.db)._usuario_tiene_referencias(self.usuario.id))
        self.assertEqual(len(response.asistencias), 1)
        self.assertEqual(response.asistencias[0].empleado_nombre, "Ana Caribe")
        self.assertEqual(response.asistencias[0].turno_nombre, "Matutino")

    def test_delivery_event_can_include_supplier_and_expected_quantity(self) -> None:
        datos = EventoCalendarioRequest(
            tipo=TipoEventoCalendario.LLEGADA_INSUMO,
            titulo="Entrega semanal",
            fecha_inicio=date(2026, 5, 13),
            insumo_id=self.insumo.id,
            proveedor_id=self.proveedor.id,
            cantidad_esperada=Decimal("12.50"),
        )
        CalendarioService(self.db).crear_evento(datos, self.usuario.id)

        result = CalendarioService(self.db).obtener_calendario(
            date(2026, 5, 13),
            date(2026, 5, 13),
        )

        event = result["eventos"][0]
        CalendarioResponse.model_validate(result)
        self.assertEqual(event["insumo_nombre"], "Pescado")
        self.assertEqual(event["insumo_unidad_medida"], "Unidad")
        self.assertEqual(event["proveedor_nombre"], "Distribuidora Caribe")
        self.assertEqual(event["cantidad_esperada"], Decimal("12.50"))
        self.assertEqual(self.db.get(Insumo, self.insumo.id).cantidad_actual, Decimal("10.00"))

    def test_event_can_be_completed_and_deleted(self) -> None:
        service = CalendarioService(self.db)
        datos = EventoCalendarioRequest(
            tipo=TipoEventoCalendario.DISPONIBILIDAD_PLATILLO,
            titulo="Plan inicial",
            fecha_inicio=date(2026, 5, 12),
            menu_item_id=self.platillo.id,
        )
        event = service.crear_evento(datos, self.usuario.id)
        updated = service.actualizar_evento(
            event.id,
            datos.model_copy(update={
                "titulo": "Plan confirmado",
                "estado": EstadoEventoCalendario.REALIZADO,
            }),
        )
        self.assertEqual(updated.titulo, "Plan confirmado")
        self.assertIsNotNone(updated.completado_en)

        service.eliminar_evento(event.id)
        self.assertIsNone(self.db.get(type(event), event.id))

    def test_schema_rejects_incomplete_or_invalid_events(self) -> None:
        with self.assertRaises(ValidationError):
            EventoCalendarioRequest(
                tipo=TipoEventoCalendario.DISPONIBILIDAD_PLATILLO,
                titulo="Sin platillo",
                fecha_inicio=date(2026, 5, 12),
            )
        with self.assertRaises(ValidationError):
            EventoCalendarioRequest(
                tipo=TipoEventoCalendario.LLEGADA_INSUMO,
                titulo="Llegada",
                fecha_inicio=date(2026, 5, 12),
                fecha_fin=date(2026, 5, 11),
                insumo_id=self.insumo.id,
            )

    def test_calendar_range_is_bounded_and_ordered(self) -> None:
        with self.assertRaises(HTTPException) as reversed_range:
            _validar_rango(date(2026, 5, 13), date(2026, 5, 12))
        self.assertEqual(reversed_range.exception.status_code, 400)

        with self.assertRaises(HTTPException) as oversized_range:
            _validar_rango(date(2026, 1, 1), date(2026, 3, 5))
        self.assertEqual(oversized_range.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
