"""
应用配置

通过 pydantic-settings 从环境变量或 .env 加载。
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    应用配置项。

    环境变量：
    - DATABASE_URL: 数据库连接串，默认 sqlite+aiosqlite
    - DEBUG: 调试模式，影响日志级别和 SQL echo
    - KUBECONFIG_ENCRYPTION_KEY: kubeconfig 加密密钥（见 crypto_utils）
    """
    APP_NAME: str = "K8s Auto Scaler Dashboard"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./k8s_dashboard.db"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
