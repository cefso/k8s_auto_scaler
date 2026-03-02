"""
扩缩容与定时任务 API

- 定时任务 CRUD
- 立即执行 Deployment/StatefulSet 扩缩容
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
)

router = APIRouter(prefix="/api/scaling", tags=["scaling"])


@router.get("/schedules", response_model=list[ScalingScheduleResponse])
async def list_schedules(
    cluster_id: int | None = None,
    db: AsyncSession = Depends(get_db),
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
):
    """创建定时扩缩容任务"""
    # 验证集群存在
    result = await db.execute(select(Cluster).where(Cluster.id == data.cluster_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="集群不存在")
    
    schedule = ScalingSchedule(**data.model_dump())
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    if schedule.is_enabled:
        add_schedule_to_scheduler(schedule)
    return schedule


@router.put("/schedules/{schedule_id}", response_model=ScalingScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScalingScheduleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新定时任务"""
    result = await db.execute(select(ScalingSchedule).where(ScalingSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(schedule, k, v)
    
    await db.commit()
    await db.refresh(schedule)
    remove_schedule_from_scheduler(schedule.id)
    if schedule.is_enabled:
        add_schedule_to_scheduler(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除定时任务"""
    result = await db.execute(select(ScalingSchedule).where(ScalingSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="任务不存在")
    sid = schedule.id
    await db.delete(schedule)
    await db.commit()
    remove_schedule_from_scheduler(sid)
    return {"message": "删除成功"}


@router.post("/scale/{cluster_id}")
async def scale_resource(
    cluster_id: int,
    body: ScaleRequest,
    db: AsyncSession = Depends(get_db),
):
    """立即执行扩缩容"""
    namespace = body.namespace
    resource_type = body.resource_type
    resource_name = body.resource_name
    replicas = body.replicas
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    
    api_client = get_api_client_for_cluster(cluster)
    
    if resource_type.lower() == "deployment":
        result = scale_deployment(api_client, namespace, resource_name, replicas)
    elif resource_type.lower() == "statefulset":
        result = scale_statefulset(api_client, namespace, resource_name, replicas)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的资源类型: {resource_type}")
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result
