"""
kubeconfig 加密工具

使用 Fernet 对称加密保护存储在数据库中的 kubeconfig 内容。
生产环境必须设置 KUBECONFIG_ENCRYPTION_KEY。
"""
import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

logger = logging.getLogger(__name__)

_fernet_key_cache: bytes | None = None


def _parse_fernet_key(raw: str) -> bytes:
    """解析 Fernet 密钥，兼容 Fernet.generate_key() 与 Helm 旧版标准 Base64。"""
    raw = raw.strip()
    if not raw:
        raise ValueError("KUBECONFIG_ENCRYPTION_KEY 为空")

    try:
        Fernet(raw.encode())
        return raw.encode()
    except Exception:
        pass

    try:
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) != 32:
            raise ValueError("decoded length is not 32")
        normalized = base64.urlsafe_b64encode(decoded)
        Fernet(normalized)
        return normalized
    except Exception as e:
        raise ValueError(
            "KUBECONFIG_ENCRYPTION_KEY 格式无效，请使用 Fernet.generate_key() 生成"
        ) from e


def validate_crypto_config() -> None:
    """启动时校验加密配置，生产环境禁止静默回退。"""
    raw = os.environ.get("KUBECONFIG_ENCRYPTION_KEY", "").strip()
    if raw:
        _parse_fernet_key(raw)
        return

    if not settings.DEBUG:
        raise ValueError(
            "生产环境必须设置 KUBECONFIG_ENCRYPTION_KEY（DEBUG=false 时不允许从 SECRET_KEY 派生）"
        )
    logger.warning(
        "未设置 KUBECONFIG_ENCRYPTION_KEY，开发模式使用 SECRET_KEY 派生密钥，仅限本地调试"
    )


def _get_fernet_key() -> bytes:
    global _fernet_key_cache
    if _fernet_key_cache is not None:
        return _fernet_key_cache

    raw = os.environ.get("KUBECONFIG_ENCRYPTION_KEY", "").strip()
    if raw:
        _fernet_key_cache = _parse_fernet_key(raw)
        return _fernet_key_cache

    if not settings.DEBUG:
        raise ValueError("生产环境必须设置 KUBECONFIG_ENCRYPTION_KEY")

    salt = b"k8s_auto_scaler_kubeconfig"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    secret = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    derived = kdf.derive(secret.encode())
    _fernet_key_cache = base64.urlsafe_b64encode(derived)
    return _fernet_key_cache


def encrypt_kubeconfig(content: str) -> str:
    f = Fernet(_get_fernet_key())
    return f.encrypt(content.encode("utf-8")).decode("ascii")


def decrypt_kubeconfig(encrypted: str) -> str:
    f = Fernet(_get_fernet_key())
    try:
        return f.decrypt(encrypted.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError(
            "kubeconfig 解密失败，请检查 KUBECONFIG_ENCRYPTION_KEY 是否与加密时一致"
        ) from e
