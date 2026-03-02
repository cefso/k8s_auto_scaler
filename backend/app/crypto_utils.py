"""
kubeconfig 加密工具

使用 Fernet 对称加密保护存储在数据库中的 kubeconfig 内容。
密钥可通过环境变量 KUBECONFIG_ENCRYPTION_KEY 配置，或从 SECRET_KEY 派生（仅开发用）。
"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_fernet_key() -> bytes:
    """
    获取 Fernet 加密密钥。

    优先级：KUBECONFIG_ENCRYPTION_KEY（格式需为 Fernet.generate_key() 输出）
          > SECRET_KEY 经 PBKDF2 派生（开发环境回退）
    """
    raw = os.environ.get("KUBECONFIG_ENCRYPTION_KEY")
    if raw:
        raw = raw.strip()
        try:
            Fernet(raw.encode())  # 验证格式
            return raw.encode()
        except Exception:
            pass
    # 从 SECRET_KEY 派生（开发回退，生产务必设置 KUBECONFIG_ENCRYPTION_KEY）
    salt = b"k8s_auto_scaler_kubeconfig"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    secret = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    derived = kdf.derive(secret.encode())
    return base64.urlsafe_b64encode(derived)


def encrypt_kubeconfig(content: str) -> str:
    """加密 kubeconfig 明文，返回 URL-safe base64 编码的密文。"""
    f = Fernet(_get_fernet_key())
    return f.encrypt(content.encode("utf-8")).decode("ascii")


def decrypt_kubeconfig(encrypted: str) -> str:
    """解密 kubeconfig 密文，返回明文 YAML 字符串。"""
    f = Fernet(_get_fernet_key())
    return f.decrypt(encrypted.encode("ascii")).decode("utf-8")
