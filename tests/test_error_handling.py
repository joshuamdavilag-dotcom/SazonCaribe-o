import unittest

from app.main import app, manejador_error_no_controlado
from starlette.requests import Request


class ErrorHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_unhandled_exception_returns_generic_message_without_debug(self) -> None:
        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/test",
            "raw_path": b"/api/v1/test",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
        })

        response = await manejador_error_no_controlado(
            request,
            RuntimeError("sensitive implementation detail"),
        )
        body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 500)
        self.assertFalse(app.debug)
        self.assertIn("Ocurrió un error inesperado.", body)
        self.assertNotIn("RuntimeError", body)
        self.assertNotIn("sensitive implementation detail", body)


if __name__ == "__main__":
    unittest.main()
