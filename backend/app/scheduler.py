"""
定时扩缩容调度器

使用 APScheduler AsyncIOScheduler，与 FastAPI 共享事件循环。
任务按 Cron 表达式触发，调用 K8s API 执行 Deployment/StatefulSet 扩缩。
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Cluster, ScalingSchedule
from app.services.k8s_service import (
    get_api_client_for_cluster,
    scale_deployment,
    scale_statefulset,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_scale_job(schedule_id: int):
    """APScheduler 回调：根据 schedule_id 查询任务并执行 K8s 扩缩容。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScalingSchedule).where(ScalingSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule or not schedule.is_enabled:
            return
        
        result = await db.execute(select(Cluster).where(Cluster.id == schedule.cluster_id))
        cluster = result.scalar_one_or_none()
        if not cluster or not cluster.is_active:
            logger.warning(f"集群 {schedule.cluster_id} 不存在或已禁用，跳过任务 {schedule.id}")
            return
        
        try:
            api_client = get_api_client_for_cluster(cluster)
            if schedule.resource_type.lower() == "deployment":
                res = scale_deployment(
                    api_client,
                    schedule.namespace,
                    schedule.resource_name,
                    schedule.target_replicas,
                )
            elif schedule.resource_type.lower() == "statefulset":
                res = scale_statefulset(
                    api_client,
                    schedule.namespace,
                    schedule.resource_name,
                    schedule.target_replicas,
                )
            else:
                logger.error(f"不支持的资源类型: {schedule.resource_type}")
                return
            
            if res["success"]:
                logger.info(
                    f"定时扩缩容成功: {schedule.namespace}/{schedule.resource_name} -> {schedule.target_replicas} 副本"
                )
            else:
                logger.error(f"定时扩缩容失败: {res['message']}")
        except Exception as e:
            logger.exception(f"定时扩缩容异常: {schedule.id} - {e}")


def add_schedule_to_scheduler(schedule: ScalingSchedule):
    """将定时任务注册到 APScheduler，job_id 为 schedule_{id}。"""
    trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone=schedule.timezone)
    scheduler.add_job(
        _run_scale_job,
        trigger=trigger,
        id=f"schedule_{schedule.id}",
        args=[schedule.id],
        replace_existing=True,
    )
    logger.info(f"已添加定时任务: {schedule.id} - {schedule.resource_name} @ {schedule.cron_expression}")


def remove_schedule_from_scheduler(schedule_id: int):
    """从 APScheduler 移除指定 schedule_id 对应的 job。"""
    try:
        scheduler.remove_job(f"schedule_{schedule_id}")
        logger.info(f"已移除定时任务: {schedule_id}")
    except Exception:
        pass
