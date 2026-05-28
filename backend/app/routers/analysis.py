"""
Kubernetes 资源分析与健康度评估 API
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Cluster
from app.services.k8s_service import get_api_client_for_cluster
from app.services.analysis_service import analyze_workload_health

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resources", tags=["analysis"])


async def _get_cluster(db: AsyncSession, cluster_id: int) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="集群已禁用")
    return cluster


@router.get("/{cluster_id}/analysis/workload-health")
async def get_workload_health_endpoint(
    cluster_id: int,
    namespace: str | None = Query(None, description="命名空间过滤（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """获取 Deployment/StatefulSet 的资源健康度分析

    返回工作负载列表，每项包含健康状态（healthy/warning/waste）和优化建议。
    - healthy: 资源配置合理
    - warning: 存在 OOMKilled 或限流风险
    - waste: 存在资源浪费
    """
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    try:
        workloads = analyze_workload_health(
            api_client=api_client,
            namespace=namespace,
        )
        return {
            "cluster_id": cluster_id,
            "namespace": namespace,
            "items": workloads,
            "total": len(workloads),
        }
    except Exception as e:
        logger.error(f"健康度分析失败: cluster={cluster.name}, 原因: {e}")
        raise HTTPException(status_code=500, detail=f"健康度分析失败: {str(e)}")
