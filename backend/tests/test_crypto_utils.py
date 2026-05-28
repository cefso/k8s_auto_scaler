import base64
import os

import pytest
from cryptography.fernet import Fernet

from app.crypto_utils import _parse_fernet_key, _unwrap_env_fernet_key


def test_parse_fernet_key_accepts_generate_key_format():
    key = Fernet.generate_key().decode()
    assert _parse_fernet_key(key) == key.encode()


def test_parse_fernet_key_accepts_standard_base64_32_bytes():
    raw = os.urandom(32)
    std = base64.b64encode(raw).decode()
    f = Fernet(_parse_fernet_key(std))
    assert f.decrypt(f.encrypt(b"hello")) == b"hello"


def test_parse_fernet_key_accepts_helm_urlsafe_style():
    raw = os.urandom(32)
    helm_style = base64.b64encode(raw).decode().replace("+", "-").replace("/", "_")
    f = Fernet(_parse_fernet_key(helm_style))
    assert f.decrypt(f.encrypt(b"hello")) == b"hello"


def test_parse_fernet_key_accepts_key_missing_padding():
    raw = os.urandom(32)
    no_pad = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    f = Fernet(_parse_fernet_key(no_pad))
    assert f.decrypt(f.encrypt(b"hello")) == b"hello"


def test_parse_fernet_key_rejects_jwt_like_key():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        _parse_fernet_key("a" * 64)


def test_unwrap_env_fernet_key_fixes_double_base64():
    real = Fernet.generate_key().decode()
    double = base64.b64encode(real.encode("ascii")).decode("ascii")
    assert len(double) > 50
    unwrapped = _unwrap_env_fernet_key(double)
    assert unwrapped == real
    Fernet(_parse_fernet_key(double))
