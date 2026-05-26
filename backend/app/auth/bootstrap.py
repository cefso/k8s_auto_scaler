"""首启创建管理员账号。"""
import logging

from sqlalchemy import func, select

from app.auth.password import hash_password
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User

logger = logging.getLogger(__name__)


async def bootstrap_admin_user() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(User))
        if count and count > 0:
            return

        username = settings.INIT_ADMIN_USERNAME.strip()
        password = settings.INIT_ADMIN_PASSWORD
        if not username or not password:
            if settings.DEBUG:
                username = username or "admin"
                password = password or "admin123"
                logger.warning("使用开发环境默认 admin 账号，生产环境请设置 INIT_ADMIN_*")
            else:
                raise RuntimeError(
                    "数据库无用户，请设置 INIT_ADMIN_USERNAME 与 INIT_ADMIN_PASSWORD 后重启"
                )

        admin = User(
            username=username,
            password_hash=hash_password(password),
            display_name="Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        logger.info("已创建初始管理员账号: %s", username)
