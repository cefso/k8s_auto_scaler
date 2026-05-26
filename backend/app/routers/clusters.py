"""
集群管理 API

- 集群 CRUD：创建、查询、更新、删除集群
- kubeconfig 以加密形式存入数据库
- 测试集群连接、更新 kubeconfig
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from kubernetes import client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.deps import CurrentUser, require_role
from app.database import get_db
from app.models import Cluster
from app.schemas import ClusterCreate, ClusterUpdate, ClusterKubeconfigUpdate, ClusterResponse
from app.crypto_utils import encrypt_kubeconfig
from app.services.k8s_service import get_api_client_for_cluster, load_k8s_client_from_content

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterResponse])
async def list_clusters(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("viewer")),
):
    result = await db.execute(select(Cluster).order_by(Cluster.id))
    return result.scalars().all()


@router.post("", response_model=ClusterResponse)
async def create_cluster(
    data: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("admin")),
):
    result = await db.execute(select(Cluster).where(Cluster.name == data.name))
    if result.scalar_one_or_none():
        logger.warning("创建集群失败: 名称 '%s' 已存在", data.name)
        raise HTTPException(status_code=400, detail="集群名称已存在")

    try:
        load_k8s_client_from_content(data.kubeconfig_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"kubeconfig 无效: {str(e)}")

    kubeconfig_encrypted = encrypt_kubeconfig(data.kubeconfig_content)
    cluster = Cluster(
        name=data.name,
        display_name=data.display_name or data.name,
        kubeconfig_encrypted=kubeconfig_encrypted,
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)
    logger.info("集群创建成功: id=%s, name=%s", cluster.id, cluster.name)
    return cluster


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("viewer")),
):
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    return cluster


@router.put("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    data: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("admin")),
):
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")

    if data.display_name is not None:
        cluster.display_name = data.display_name
    if data.is_active is not None:
        cluster.is_active = data.is_active

    await db.commit()
    await db.refresh(cluster)
    return cluster


@router.put("/{cluster_id}/kubeconfig", response_model=ClusterResponse)
async def update_cluster_kubeconfig(
    cluster_id: int,
    data: ClusterKubeconfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("admin")),
):
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")

    try:
        load_k8s_client_from_content(data.kubeconfig_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"kubeconfig 无效: {str(e)}")

    cluster.kubeconfig_encrypted = encrypt_kubeconfig(data.kubeconfig_content)
    await db.commit()
    await db.refresh(cluster)
    return cluster


@router.delete("/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("admin")),
):
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")

    await db.delete(cluster)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{cluster_id}/test")
async def test_cluster_connection(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_role("viewer")),
):
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")

    try:
        api_client = get_api_client_for_cluster(cluster)
        v1 = client.CoreV1Api(api_client)
        v1.list_namespace()
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")
