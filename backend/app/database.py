"""
数据库配置与迁移

- 使用 SQLAlchemy 异步引擎 (aiosqlite)
- 启动时自动执行 kubeconfig 存储迁移（旧版文件路径 -> 加密存储）
"""
import re
import sqlite3
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from app.crypto_utils import encrypt_kubeconfig


# 异步引擎，echo=True 时打印 SQL（DEBUG 模式）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式模型基类，所有 model 继承此类。"""
    pass


async def get_db():
    """FastAPI 依赖：获取异步数据库会话；由路由显式 commit。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """根据 models 定义创建所有表（若不存在）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _get_sqlite_path() -> Path:
    """从 DATABASE_URL 解析 SQLite 文件路径"""
    url = settings.DATABASE_URL
    m = re.search(r"sqlite\+?(?:\w+)?:///(.+)$", url)
    if m:
        return Path(m.group(1))
    return Path("./k8s_dashboard.db")


async def migrate_kubeconfig_to_encrypted():
    """
    迁移旧版 clusters 表：将 kubeconfig_path 指向的本地文件内容
    读取并加密后写入新列 kubeconfig_encrypted。
    仅当表存在且为旧 schema 时执行，执行一次后跳过。
    """
    db_path = _get_sqlite_path()
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("PRAGMA table_info(clusters)")
        cols = {row[1] for row in cur.fetchall()}
        # 已是新 schema 或表结构异常，跳过
        if "kubeconfig_encrypted" in cols:
            return
        if "kubeconfig_path" not in cols:
            conn.close()
            return
        conn.execute("ALTER TABLE clusters ADD COLUMN kubeconfig_encrypted TEXT")
        cur = conn.execute("SELECT id, kubeconfig_path FROM clusters WHERE kubeconfig_path IS NOT NULL AND kubeconfig_path != ''")
        for row in cur.fetchall():  # 逐条读取文件、加密、更新
            cid, path = row[0], row[1]
            try:
                content = Path(path).read_text(encoding="utf-8")
                encrypted = encrypt_kubeconfig(content)
                conn.execute("UPDATE clusters SET kubeconfig_encrypted = ? WHERE id = ?", (encrypted, cid))
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
