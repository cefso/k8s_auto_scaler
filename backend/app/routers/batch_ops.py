"""
Kubernetes 批量操作 API

提供：
- POST /api/batch/restart-pods - 批量重启 Pod
- POST /api/batch/delete-pods - 批量删除 Pod
- POST /api/batch/update-labels - 批量更新 Pod Labels
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, require_role
from app.database import get_db
from app.models import Cluster
from app.services.k8s_service import get_api_client_for_cluster
from app.services.batch_service import restart_pods, delete_pods, update_pod_labels
from app.routers.audit import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchItem(BaseModel):
    namespace: str
    name: str


class BatchRestartPodsRequest(BaseModel):
    cluster_id: int
    items: list[BatchItem]


class BatchDeletePodsRequest(BaseModel):
    cluster_id: int
    items: list[BatchItem]


class BatchUpdateLabelsRequest(BaseModel):
    cluster_id: int
    items: list[BatchItem]
    labels: dict[str, str]


async def _get_cluster(db: AsyncSession, cluster_id: int) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="集群已禁用")
    return cluster


@router.post("/restart-pods")
async def batch_restart_pods(
    request: BatchRestartPodsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """批量重启 Pod（通过删除 Pod 实现，Kubernetes 会自动重新创建）"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    cluster = await _get_cluster(db, request.cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    items = [{"namespace": item.namespace, "name": item.name} for item in request.items]
    result = restart_pods(api_client, items)

    # 审计日志
    for item in result["success"]:
        await create_audit_log(
            action="restart",
            resource_type="Pod",
            resource_name=item["name"],
            namespace=item["namespace"],
            cluster_id=request.cluster_id,
            operator=current_user.username,
            details={"batch": True},
        )

    logger.info(
        f"批量重启 Pod 完成: cluster={cluster.name}, "
        f"total={result['total']}, success={len(result['success'])}, failed={len(result['failed'])}"
    )

    return result


@router.post("/delete-pods")
async def batch_delete_pods(
    request: BatchDeletePodsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """批量删除 Pod"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    cluster = await _get_cluster(db, request.cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    items = [{"namespace": item.namespace, "name": item.name} for item in request.items]
    result = delete_pods(api_client, items)

    # 审计日志
    for item in result["success"]:
        await create_audit_log(
            action="delete",
            resource_type="Pod",
            resource_name=item["name"],
            namespace=item["namespace"],
            cluster_id=request.cluster_id,
            operator=current_user.username,
            details={"batch": True},
        )

    logger.info(
        f"批量删除 Pod 完成: cluster={cluster.name}, "
        f"total={result['total']}, success={len(result['success'])}, failed={len(result['failed'])}"
    )

    return result


@router.post("/update-labels")
async def batch_update_labels(
    request: BatchUpdateLabelsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("operator")),
):
    """批量更新 Pod 的 Labels"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")
    if not request.labels:
        raise HTTPException(status_code=400, detail="labels 不能为空")

    cluster = await _get_cluster(db, request.cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    items = [{"namespace": item.namespace, "name": item.name} for item in request.items]
    result = update_pod_labels(api_client, items, request.labels)

    # 审计日志
    for item in result["success"]:
        await create_audit_log(
            action="update",
            resource_type="Pod",
            resource_name=item["name"],
            namespace=item["namespace"],
            cluster_id=request.cluster_id,
            operator=current_user.username,
            details={"labels": request.labels, "batch": True},
        )

    logger.info(
        f"批量更新 Labels 完成: cluster={cluster.name}, labels={request.labels}, "
        f"total={result['total']}, success={len(result['success'])}, failed={len(result['failed'])}"
    )

    return result
