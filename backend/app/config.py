"""
应用配置

通过 pydantic-settings 从环境变量或 .env 加载。
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "K8s Auto Scaler Dashboard"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./k8s_dashboard.db"

    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    INIT_ADMIN_USERNAME: str = "admin"
    INIT_ADMIN_PASSWORD: str = "admin123"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
