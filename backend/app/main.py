"""
K8s Auto Scaler Dashboard 主应用入口

- 启动时初始化数据库、执行迁移、加载定时任务
- 关闭时停止调度器
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.auth.bootstrap import bootstrap_admin_user
from app.auth.deps import get_current_user
from app.config import settings
from app.crypto_utils import validate_crypto_config
from app.database import init_db, migrate_kubeconfig_to_encrypted, AsyncSessionLocal
from app.models import Cluster, ScalingSchedule
from app.routers import (
    auth,
    users,
    clusters,
    resources,
    scaling,
    logs,
    analysis,
    batch_ops,
    search,
    audit,
)
from app.scheduler import scheduler, add_schedule_to_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_auth_required = [Depends(get_current_user)]


async def load_schedules_on_startup():
    """从数据库加载所有 is_enabled=True 的定时任务并注册到 APScheduler。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScalingSchedule).where(ScalingSchedule.is_enabled == True)
        )
        schedules = result.scalars().all()
        for s in schedules:
            add_schedule_to_scheduler(s)
    logger.info("已加载 %s 个定时扩缩容任务", len(schedules))


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_crypto_config()
    await init_db()
    await migrate_kubeconfig_to_encrypted()
    await bootstrap_admin_user()
    if not scheduler.running:
        scheduler.start()
        await load_schedules_on_startup()
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    description="K8s 集群资源管理与定时扩缩容 Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router, dependencies=_auth_required)
app.include_router(clusters.router, dependencies=_auth_required)
app.include_router(resources.router, dependencies=_auth_required)
app.include_router(scaling.router, dependencies=_auth_required)
# logs 路由的 WebSocket 通过 query access_token 鉴权，不可挂 HTTP Bearer 依赖
app.include_router(logs.router)
app.include_router(analysis.router, dependencies=_auth_required)
app.include_router(batch_ops.router, dependencies=_auth_required)
app.include_router(search.router, dependencies=_auth_required)
app.include_router(audit.router, dependencies=_auth_required)


@app.get("/")
async def root():
    """健康检查与 API 文档入口。"""
    return {"message": "K8s Auto Scaler Dashboard API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8082,
        reload=settings.DEBUG,
    )
