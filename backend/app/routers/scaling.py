"""
扩缩容与定时任务 API

- 定时任务 CRUD：创建、查询、更新、删除定时扩缩容任务
- 立即执行 Deployment/StatefulSet 扩缩容
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.deps import CurrentUser, require_role
from app.database import get_db
from app.scheduler import add_schedule_to_scheduler, remove_schedule_from_scheduler
from app.models import Cluster, ScalingSchedule
from app.schemas import (
    ScalingScheduleCreate,
    ScalingScheduleUpdate,
    ScalingScheduleResponse,
    ScaleRequest,
)
from app.services.k8s_service import (
    get_api_client_for_cluster,
    scale_deployment,
    scale_statefulset,
    validate_workload_exists,
)
from app.routers.audit import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scaling", tags=["scaling"])


@router.get("/schedules", response_model=list[ScalingScheduleResponse])
async def list_schedules(
    cluster_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("viewer")),
):
    """列出所有定时扩缩容任务"""
    q = select(ScalingSchedule).join(Cluster)
    if cluster_id:
        q = q.where(ScalingSchedule.cluster_id == cluster_id)
    q = q.order_by(ScalingSchedule.id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/schedules", response_model=ScalingScheduleResponse)
async def create_schedule(
    data: ScalingScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """创建定时扩缩容任务"""
    # 验证集群存在
    result = await db.execute(select(Cluster).where(Cluster.id == data.cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"创建定时任务失败: 集群 id={data.cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    api_client = get_api_client_for_cluster(cluster)
    try:
        validate_workload_exists(
            api_client, data.resource_type, data.namespace, data.resource_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    schedule = ScalingSchedule(**data.model_dump())
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    if schedule.is_enabled:
        try:
            add_schedule_to_scheduler(schedule)
        except Exception as e:
            await db.delete(schedule)
            await db.commit()
            raise HTTPException(status_code=400, detail=f"定时任务注册失败: {e}")

    await create_audit_log(
        action="create",
        resource_type="ScalingSchedule",
        resource_name=f"{schedule.namespace}/{schedule.resource_name}",
        namespace=schedule.namespace,
        cluster_id=schedule.cluster_id,
        operator=current_user.username,
        details={
            "schedule_id": schedule.id,
            "target_replicas": schedule.target_replicas,
            "cron_expression": schedule.cron_expression,
        },
    )

    logger.info(f"定时任务创建成功: id={schedule.id}, cluster={cluster.name}, "
                 f"resource={schedule.namespace}/{schedule.resource_name}, "
                 f"replicas={schedule.target_replicas}, cron={schedule.cron_expression}")
    return schedule


@router.put("/schedules/{schedule_id}", response_model=ScalingScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScalingScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """更新定时任务（目标副本数、Cron 表达式、启用状态等）"""
    result = await db.execute(select(ScalingSchedule).where(ScalingSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        logger.warning(f"更新定时任务失败: id={schedule_id} 不存在")
        raise HTTPException(status_code=404, detail="任务不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(schedule, k, v)

    result = await db.execute(select(Cluster).where(Cluster.id == schedule.cluster_id))
    cluster = result.scalar_one_or_none()
    if cluster:
        api_client = get_api_client_for_cluster(cluster)
        try:
            validate_workload_exists(
                api_client,
                schedule.resource_type,
                schedule.namespace,
                schedule.resource_name,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    await db.refresh(schedule)
    remove_schedule_from_scheduler(schedule.id)
    if schedule.is_enabled:
        try:
            add_schedule_to_scheduler(schedule)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"定时任务注册失败: {e}")

    await create_audit_log(
        action="update",
        resource_type="ScalingSchedule",
        resource_name=f"{schedule.namespace}/{schedule.resource_name}",
        namespace=schedule.namespace,
        cluster_id=schedule.cluster_id,
        operator=current_user.username,
        details={"schedule_id": schedule.id, "updates": data.model_dump(exclude_unset=True)},
    )

    logger.info(f"定时任务更新成功: id={schedule.id}, resource={schedule.namespace}/{schedule.resource_name}")
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """删除定时任务"""
    result = await db.execute(select(ScalingSchedule).where(ScalingSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        logger.warning(f"删除定时任务失败: id={schedule_id} 不存在")
        raise HTTPException(status_code=404, detail="任务不存在")

    sid = schedule.id
    schedule_info = {
        "schedule_id": sid,
        "namespace": schedule.namespace,
        "resource_name": schedule.resource_name,
        "cluster_id": schedule.cluster_id,
    }
    await db.delete(schedule)
    await db.commit()
    remove_schedule_from_scheduler(sid)

    # 审计日志
    await create_audit_log(
        action="delete",
        resource_type="ScalingSchedule",
        resource_name=f"{schedule_info['namespace']}/{schedule_info['resource_name']}",
        namespace=schedule_info["namespace"],
        cluster_id=schedule_info["cluster_id"],
        operator=current_user.username,
        details=schedule_info,
    )

    logger.info(f"定时任务已删除: id={sid}")
    return {"message": "删除成功"}


@router.post("/scale/{cluster_id}")
async def scale_resource(
    cluster_id: int,
    body: ScaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """立即执行扩缩容"""
    namespace = body.namespace
    resource_type = body.resource_type
    resource_name = body.resource_name
    replicas = body.replicas

    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"立即扩缩容失败: 集群 id={cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    api_client = get_api_client_for_cluster(cluster)

    if resource_type.lower() == "deployment":
        result = scale_deployment(api_client, namespace, resource_name, replicas)
    elif resource_type.lower() == "statefulset":
        result = scale_statefulset(api_client, namespace, resource_name, replicas)
    else:
        logger.warning(f"立即扩缩容失败: 不支持的资源类型 {resource_type}")
        raise HTTPException(status_code=400, detail=f"不支持的资源类型: {resource_type}")

    if not result["success"]:
        logger.warning(f"立即扩缩容失败: cluster={cluster.name}, "
                       f"resource={namespace}/{resource_name}, 原因: {result['message']}")
        raise HTTPException(status_code=400, detail=result["message"])

    # 审计日志
    await create_audit_log(
        action="scale",
        resource_type=resource_type,
        resource_name=resource_name,
        namespace=namespace,
        cluster_id=cluster_id,
        operator=current_user.username,
        details={"replicas": replicas},
    )

    logger.info(f"立即扩缩容成功: cluster={cluster.name}, "
                f"resource={namespace}/{resource_name}, replicas={replicas}")
    return result
