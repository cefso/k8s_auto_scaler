"""
K8s Auto Scaler Dashboard 主应用入口

- 启动时初始化数据库、执行迁移、加载定时任务
- 关闭时停止调度器
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import init_db, migrate_kubeconfig_to_encrypted, AsyncSessionLocal
from app.models import Cluster, ScalingSchedule
from app.routers import clusters, resources, scaling
from app.scheduler import scheduler, add_schedule_to_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def load_schedules_on_startup():
    """从数据库加载所有 is_enabled=True 的定时任务并注册到 APScheduler。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScalingSchedule).where(ScalingSchedule.is_enabled == True)
        )
        schedules = result.scalars().all()
        for s in schedules:
            add_schedule_to_scheduler(s)
    logger.info(f"已加载 {len(schedules)} 个定时扩缩容任务")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期：启动时初始化 DB、迁移、调度器；关闭时停止调度器。"""
    await init_db()
    await migrate_kubeconfig_to_encrypted()
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clusters.router)
app.include_router(resources.router)
app.include_router(scaling.router)


@app.get("/")
async def root():
    """健康检查与 API 文档入口。"""
    return {"message": "K8s Auto Scaler Dashboard API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
