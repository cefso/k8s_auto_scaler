import base64
import os

from cryptography.fernet import Fernet

from app.crypto_utils import _parse_fernet_key


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
