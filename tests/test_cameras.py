from datetime import datetime, timedelta, timezone
from decimal import Decimal
from tempfile import TemporaryDirectory
import base64
import hashlib
import hmac
import time
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import Base
from app.models.camera import Camera, CameraClip
from app.models.personal import Empleado, Puesto, Usuario
from app.schemas.camera import CameraAccessUpdate, CameraCreate, CameraUpdate
from app.services.camera_service import CameraService


class CameraServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(
            _env_file=None,
            CAMERA_BRIDGE_BASE_URL="https://cameras.example.test",
            CAMERA_STORAGE_DIR=self.temporary_directory.name,
        )
        self.service = CameraService(self.db, self.settings)

        puesto = Puesto(nombre="Vendedor", salario_base=Decimal("1000.00"))
        self.db.add(puesto)
        self.db.flush()
        empleado = Empleado(
            nombre="Ana",
            apellido="Caribe",
            cedula_identidad="CAM-001",
            puesto_id=puesto.id,
            fecha_ingreso=datetime(2025, 1, 1).date(),
            salario_base=Decimal("1000.00"),
        )
        self.db.add(empleado)
        self.db.flush()
        self.vendedor = Usuario(
            username="camera_user",
            password_hash="test",
            rol="Vendedor",
            empleado_id=empleado.id,
            activo=True,
            turno_habilitado=True,
        )
        self.admin = Usuario(
            username="camera_admin",
            password_hash="test",
            rol="Administrador",
            empleado_id=empleado.id,
            activo=True,
            turno_habilitado=True,
        )
        self.db.add(self.vendedor)
        self.db.flush()
        self.admin.empleado_id = self._crear_empleado(puesto.id, "CAM-002")
        self.db.add(self.admin)
        self.db.commit()

    def _crear_empleado(self, puesto_id: int, cedula: str) -> int:
        empleado = Empleado(
            nombre="Luis",
            apellido="Caribe",
            cedula_identidad=cedula,
            puesto_id=puesto_id,
            fecha_ingreso=datetime(2025, 1, 1).date(),
            salario_base=Decimal("1000.00"),
        )
        self.db.add(empleado)
        self.db.flush()
        return empleado.id

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def _crear_camara(self) -> Camera:
        self.service.crear_camara(
            CameraCreate(nombre="Entrada principal", slug="entrada-principal")
        )
        return self.db.query(Camera).filter_by(slug="entrada-principal").one()

    def test_user_grants_produce_short_lived_camera_scoped_tokens(self) -> None:
        camera = self._crear_camara()
        with self.assertRaises(HTTPException) as denied:
            self.service.emitir_token_stream(camera.id, self.vendedor)
        self.assertEqual(denied.exception.status_code, 404)

        result = self.service.actualizar_accesos(
            camera.id, CameraAccessUpdate(usuario_ids=[self.vendedor.id])
        )
        self.assertEqual(result["usuario_ids"], [self.vendedor.id])
        token = self.service.emitir_token_stream(camera.id, self.vendedor)["token"]

        self.service.autorizar_puente(
            "entrada-principal",
            token,
            action="read",
            path="entrada-principal",
        )
        with self.assertRaises(HTTPException) as denied_write:
            self.service.autorizar_puente(
                "entrada-principal",
                token,
                action="publish",
                path="entrada-principal",
            )
        self.assertEqual(denied_write.exception.status_code, 401)

        self.service.actualizar_accesos(camera.id, CameraAccessUpdate(usuario_ids=[]))
        with self.assertRaises(HTTPException) as revoked:
            self.service.autorizar_puente(
                "entrada-principal",
                token,
                action="read",
                path="entrada-principal",
            )
        self.assertEqual(revoked.exception.status_code, 401)

    def test_manual_clip_chunks_are_ordered_private_and_reproducible(self) -> None:
        camera = self._crear_camara()
        self.service.actualizar_accesos(
            camera.id, CameraAccessUpdate(usuario_ids=[self.vendedor.id])
        )
        clip = self.service.iniciar_clip(camera.id, self.vendedor, "video/webm")
        first_chunk = bytes.fromhex("1a45dfa3") + b"test-video"

        saved = self.service.guardar_fragmento(
            camera.id, clip["id"], 0, self.vendedor, first_chunk
        )
        self.assertEqual(saved["fragmentos_recibidos"], 1)
        with self.assertRaises(HTTPException) as out_of_order:
            self.service.guardar_fragmento(
                camera.id, clip["id"], 0, self.vendedor, first_chunk
            )
        self.assertEqual(out_of_order.exception.status_code, 409)

        result = self.service.finalizar_clip(camera.id, clip["id"], self.vendedor)
        self.assertEqual(result["bytes_guardados"], len(first_chunk))
        path, mime_type = self.service.obtener_video_clip(clip["id"], self.vendedor)
        self.assertEqual(mime_type, "video/webm")
        self.assertEqual(path.read_bytes(), first_chunk)
        self.assertEqual(len(self.service.listar_clips(self.vendedor)), 1)

        self.service.cancelar_clip(clip["id"], self.vendedor)
        self.assertFalse(path.exists())
        self.assertEqual(self.service.listar_clips(self.vendedor), [])

    def test_expired_clips_are_deleted_from_database_and_persistent_storage(self) -> None:
        camera = self._crear_camara()
        clip = CameraClip(
            id="00000000-0000-0000-0000-000000000001",
            camara_id=camera.id,
            usuario_id=self.vendedor.id,
            usuario_nombre=self.vendedor.username,
            mime_type="video/webm",
            estado="COMPLETADO",
            bytes_guardados=8,
            creado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8),
            finalizado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8),
        )
        self.db.add(clip)
        self.db.commit()
        path = self.service._clip_path(clip)
        path.write_bytes(b"expired")

        self.assertEqual(self.service.limpiar_clips_vencidos(), 1)
        self.assertIsNone(self.db.get(CameraClip, clip.id))
        self.assertFalse(path.exists())

    def test_camera_registration_rejects_public_http_bridge_urls(self) -> None:
        camera = self._crear_camara()
        self.service.settings.CAMERA_BRIDGE_BASE_URL = "http://cameras.example.test"

        with self.assertRaises(HTTPException) as invalid_origin:
            self.service.emitir_token_stream(camera.id, self.admin)

        self.assertEqual(invalid_origin.exception.status_code, 503)

    def test_camera_update_rejects_duplicate_bridge_identifiers(self) -> None:
        first = self._crear_camara()
        second = self.service.crear_camara(
            CameraCreate(nombre="Caja", slug="caja")
        )

        with self.assertRaises(HTTPException) as duplicate:
            self.service.actualizar_camara(
                first.id, CameraUpdate(slug=second["slug"])
            )

        self.assertEqual(duplicate.exception.status_code, 409)

    def test_turn_credentials_are_generated_for_five_minutes(self) -> None:
        camera = self._crear_camara()
        self.service.settings.CAMERA_ICE_SERVERS_JSON = (
            '[{"urls":"turns:turn.example.test:5349"}]'
        )
        self.service.settings.CAMERA_TURN_SHARED_SECRET = "test-turn-secret"

        result = self.service.emitir_token_stream(camera.id, self.admin)
        ice_server = result["ice_servers"][0]
        expiry, user_id = ice_server["username"].split(":")
        expected_credential = base64.b64encode(
            hmac.new(
                b"test-turn-secret",
                ice_server["username"].encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("ascii")

        self.assertEqual(user_id, str(self.admin.id))
        self.assertGreater(int(expiry), int(time.time()))
        self.assertLessEqual(int(expiry) - int(time.time()), 300)
        self.assertEqual(ice_server["credential"], expected_credential)


if __name__ == "__main__":
    unittest.main()
