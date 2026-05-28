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


def _unwrap_env_fernet_key(raw: str) -> str:
    """环境变量中的密钥；兼容 Helm Secret 误双层 Base64 写入的情况。"""
    s = raw.strip().strip('"').strip("'")
    for _ in range(2):
        try:
            Fernet(s.encode("ascii"))
            return s
        except Exception:
            pass
        try:
            inner = base64.b64decode(s.encode("ascii"), validate=True).decode("ascii")
        except Exception:
            break
        if inner == s or not inner:
            break
        s = inner
    return s


def _parse_fernet_key(raw: str) -> bytes:
    """解析 Fernet 密钥，兼容 Fernet.generate_key()、标准/URL-safe Base64 及缺填充情况。"""
    raw = _unwrap_env_fernet_key(raw)
    if not raw:
        raise ValueError("KUBECONFIG_ENCRYPTION_KEY 为空")

    candidates: list[str] = [raw]
    padding = "=" * (-len(raw) % 4)
    if padding:
        candidates.append(raw + padding)

    for candidate in candidates:
        try:
            Fernet(candidate.encode("ascii"))
            return candidate.encode("ascii")
        except Exception:
            pass

    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        for candidate in candidates:
            try:
                decoded = decoder(candidate.encode("ascii"))
                if len(decoded) != 32:
                    continue
                normalized = base64.urlsafe_b64encode(decoded)
                Fernet(normalized)
                return normalized
            except Exception:
                continue

    hint = ""
    if len(raw) == 64 and raw.replace("-", "").replace("_", "").isalnum():
        hint = "（疑似误用了 JWT_SECRET_KEY，两者不可混用）"
    elif len(raw) == 43:
        hint = "（疑似缺少 Base64 末尾填充 =）"
    raise ValueError(
        f"KUBECONFIG_ENCRYPTION_KEY 格式无效（长度 {len(raw)}）{hint}，"
        "请使用 python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" 生成"
    )


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
