import bcrypt
import pytest
from pydantic import ValidationError

from app.core.security import obtener_password_hash, verificar_password
from app.schemas.personal import PasswordResetRequest, UsuarioCreate


def test_password_hash_round_trip_accepts_up_to_72_utf8_bytes():
    password = "a" * 70 + "é"

    hashed = obtener_password_hash(password)

    assert verificar_password(password, hashed)


def test_new_password_rejects_more_than_72_utf8_bytes():
    with pytest.raises(ValueError, match="72 bytes UTF-8"):
        obtener_password_hash("a" * 73)

    with pytest.raises(ValidationError, match="72 bytes UTF-8"):
        PasswordResetRequest(nueva_password="a" * 73)

    with pytest.raises(ValidationError, match="72 bytes UTF-8"):
        UsuarioCreate(
            username="empleado01",
            password="a" * 73,
            rol="Vendedor",
            empleado_id=1,
        )


def test_login_verification_preserves_legacy_bcrypt_truncation():
    password = "a" * 72 + "different-suffix"
    legacy_hash = bcrypt.hashpw(
        password.encode("utf-8")[:72],
        bcrypt.gensalt(),
    ).decode("utf-8")

    assert verificar_password(password, legacy_hash)
