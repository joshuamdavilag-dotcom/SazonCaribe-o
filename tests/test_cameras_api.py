"""Pruebas HTTP de integración para las rutas del módulo de cámaras."""

from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.endpoints.cameras import get_camera_service, router
from app.core.config import Settings
from app.core.database import Base
from app.core.security import crear_access_token
from app.models.personal import Empleado, Puesto, Usuario
from app.services.camera_service import CameraService


class CameraApiIntegrationTests(unittest.TestCase):
    """Ejercita autenticación, RBAC, acceso a streams y ciclo de clips por HTTP."""

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(
            _env_file=None,
            CAMERA_BRIDGE_BASE_URL="https://cameras.example.test",
            CAMERA_STORAGE_DIR=self.temporary_directory.name,
        )

        puesto = Puesto(nombre="Vendedor", salario_base=Decimal("1000.00"))
        self.db.add(puesto)
        self.db.flush()
        self.seller = self._create_user(puesto.id, "api_seller", "Vendedor", "API-001")
        self.admin = self._create_user(
            puesto.id, "api_admin", "Administrador", "API-002"
        )
        self.db.commit()

        self.admin_headers = self._auth_headers(self.admin)
        self.seller_headers = self._auth_headers(self.seller)
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/cameras")
        self.app.dependency_overrides[get_db] = self._override_db
        self.app.dependency_overrides[get_camera_service] = self._override_service
        self.client = TestClient(self.app)
        self.request_count = 0

    def _create_user(
        self, puesto_id: int, username: str, role: str, national_id: str
    ) -> Usuario:
        employee = Empleado(
            nombre="Prueba",
            apellido=username,
            cedula_identidad=national_id,
            puesto_id=puesto_id,
            fecha_ingreso=date(2025, 1, 1),
            salario_base=Decimal("1000.00"),
        )
        self.db.add(employee)
        self.db.flush()
        user = Usuario(
            username=username,
            password_hash="integration-test",
            rol=role,
            empleado_id=employee.id,
            activo=True,
            turno_habilitado=True,
        )
        self.db.add(user)
        self.db.flush()
        return user

    @staticmethod
    def _auth_headers(user: Usuario) -> dict[str, str]:
        token = crear_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    def _override_db(self):
        yield self.db

    def _override_service(self) -> CameraService:
        return CameraService(self.db, self.settings)

    def _request(self, method: str, path: str, **kwargs):
        self.request_count += 1
        return self.client.request(method, path, **kwargs)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_camera_routes_accept_and_reject_thirty_http_requests(self) -> None:
        """Verifica exactamente 30 respuestas HTTP en el flujo de administración y clips."""
        base = "/api/v1/cameras"

        # 1-5: autenticación, listados y almacenamiento sin cámaras.
        response = self._request("GET", f"{base}/")
        self.assertEqual(response.status_code, 401)
        response = self._request("GET", f"{base}/", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        response = self._request(
            "GET", f"{base}/eligible-users", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([user["id"] for user in response.json()], [self.seller.id])
        response = self._request("GET", f"{base}/storage", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["clips"], 0)
        response = self._request("GET", f"{base}/clips", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        # 6-14: validación de entrada y administración protegida por rol.
        response = self._request(
            "POST",
            f"{base}/",
            headers=self.admin_headers,
            json={"nombre": "Entrada", "slug": "Entrada"},
        )
        self.assertEqual(response.status_code, 422)
        response = self._request(
            "POST",
            f"{base}/",
            headers=self.admin_headers,
            json={"nombre": "Entrada principal", "slug": "entrada-principal"},
        )
        self.assertEqual(response.status_code, 201)
        camera_id = response.json()["id"]
        self.assertEqual(response.json()["stream_url"], "https://cameras.example.test/entrada-principal/whep")
        response = self._request("GET", f"{base}/", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        response = self._request(
            "POST",
            f"{base}/",
            headers=self.admin_headers,
            json={"nombre": "Duplicada", "slug": "entrada-principal"},
        )
        self.assertEqual(response.status_code, 409)
        response = self._request(
            "PATCH",
            f"{base}/999999",
            headers=self.admin_headers,
            json={"nombre": "No existe"},
        )
        self.assertEqual(response.status_code, 404)
        response = self._request(
            "POST",
            f"{base}/",
            headers=self.seller_headers,
            json={"nombre": "Sin permiso", "slug": "sin-permiso"},
        )
        self.assertEqual(response.status_code, 403)
        response = self._request(
            "PATCH",
            f"{base}/{camera_id}",
            headers=self.admin_headers,
            json={"activa": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["activa"])
        response = self._request(
            "POST", f"{base}/{camera_id}/stream-token", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 404)
        response = self._request(
            "PATCH",
            f"{base}/{camera_id}",
            headers=self.admin_headers,
            json={"activa": True},
        )
        self.assertEqual(response.status_code, 200)

        # 15-21: permisos individuales, emisión de token y autorización del puente.
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/access",
            headers=self.admin_headers,
            json={"usuario_ids": [999999]},
        )
        self.assertEqual(response.status_code, 400)
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/access",
            headers=self.admin_headers,
            json={"usuario_ids": [self.seller.id]},
        )
        self.assertEqual(response.status_code, 200)
        response = self._request(
            "POST",
            f"{base}/{camera_id}/stream-token",
            headers=self.seller_headers,
        )
        self.assertEqual(response.status_code, 200)
        stream_token = response.json()["token"]
        self.assertEqual(response.json()["expira_en_segundos"], 300)
        response = self._request(
            "POST",
            f"{base}/authorize",
            json={
                "user": "entrada-principal",
                "password": stream_token,
                "action": "read",
                "path": "entrada-principal",
            },
        )
        self.assertEqual(response.status_code, 200)
        response = self._request(
            "POST",
            f"{base}/authorize",
            json={
                "user": "entrada-principal",
                "password": stream_token,
                "action": "publish",
                "path": "entrada-principal",
            },
        )
        self.assertEqual(response.status_code, 401)
        response = self._request(
            "POST",
            f"{base}/{camera_id}/clips",
            headers=self.seller_headers,
            json={"mime_type": "video/avi"},
        )
        self.assertEqual(response.status_code, 422)

        # 22-28: grabación fragmentada, validación de secuencia, reproducción.
        response = self._request(
            "POST",
            f"{base}/{camera_id}/clips",
            headers=self.seller_headers,
            json={"mime_type": "video/webm"},
        )
        self.assertEqual(response.status_code, 201)
        clip_id = response.json()["id"]
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/clips/{clip_id}/chunks/0",
            headers=self.seller_headers,
            content=b"invalid-video",
        )
        self.assertEqual(response.status_code, 400)
        video_chunk = bytes.fromhex("1a45dfa3") + b"integration-video"
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/clips/{clip_id}/chunks/0",
            headers=self.seller_headers,
            content=video_chunk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fragmentos_recibidos"], 1)
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/clips/{clip_id}/chunks/0",
            headers=self.seller_headers,
            content=video_chunk,
        )
        self.assertEqual(response.status_code, 409)
        response = self._request(
            "POST",
            f"{base}/{camera_id}/clips/{clip_id}/finish",
            headers=self.seller_headers,
        )
        self.assertEqual(response.status_code, 200)
        response = self._request("GET", f"{base}/clips", headers=self.seller_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [clip_id])
        response = self._request(
            "GET",
            f"{base}/clips/{clip_id}/video",
            headers=self.seller_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, video_chunk)
        self.assertEqual(response.headers["content-type"], "video/webm")

        # 29-30: revocar permisos también bloquea el acceso a clips históricos.
        response = self._request(
            "PUT",
            f"{base}/{camera_id}/access",
            headers=self.admin_headers,
            json={"usuario_ids": []},
        )
        self.assertEqual(response.status_code, 200)
        response = self._request("GET", f"{base}/clips", headers=self.seller_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        response = self._request(
            "GET",
            f"{base}/clips/{clip_id}/video",
            headers=self.seller_headers,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.request_count, 30)


if __name__ == "__main__":
    unittest.main()
