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

from app.database import get_db
from app.models import Cluster
from app.schemas import ClusterCreate, ClusterUpdate, ClusterKubeconfigUpdate, ClusterResponse
from app.crypto_utils import encrypt_kubeconfig
from app.services.k8s_service import get_api_client_for_cluster

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterResponse])
async def list_clusters(db: AsyncSession = Depends(get_db)):
    """列出所有集群"""
    result = await db.execute(select(Cluster).order_by(Cluster.id))
    clusters = result.scalars().all()
    return clusters


@router.post("", response_model=ClusterResponse)
async def create_cluster(data: ClusterCreate, db: AsyncSession = Depends(get_db)):
    """添加新集群 (kubeconfig 加密存储在数据库)"""
    # 检查名称是否已存在
    result = await db.execute(select(Cluster).where(Cluster.name == data.name))
    if result.scalar_one_or_none():
        logger.warning(f"创建集群失败: 名称 '{data.name}' 已存在")
        raise HTTPException(status_code=400, detail="集群名称已存在")

    kubeconfig_encrypted = encrypt_kubeconfig(data.kubeconfig_content)
    cluster = Cluster(
        name=data.name,
        display_name=data.display_name or data.name,
        kubeconfig_encrypted=kubeconfig_encrypted,
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)
    logger.info(f"集群创建成功: id={cluster.id}, name={cluster.name}")
    return cluster


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """获取集群详情"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    return cluster


@router.put("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int, data: ClusterUpdate, db: AsyncSession = Depends(get_db)
):
    """更新集群（显示名称、启用/禁用状态）"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"更新集群失败: id={cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    if data.display_name is not None:
        cluster.display_name = data.display_name
    if data.is_active is not None:
        cluster.is_active = data.is_active
        logger.info(f"集群状态更新: id={cluster_id}, is_active={data.is_active}")

    await db.commit()
    await db.refresh(cluster)
    logger.info(f"集群更新成功: id={cluster_id}, name={cluster.name}")
    return cluster


@router.put("/{cluster_id}/kubeconfig", response_model=ClusterResponse)
async def update_cluster_kubeconfig(
    cluster_id: int, data: ClusterKubeconfigUpdate, db: AsyncSession = Depends(get_db)
):
    """更新集群的 kubeconfig（加密存储）"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"更新 kubeconfig 失败: 集群 id={cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    # 验证新的 kubeconfig 是否有效
    try:
        from app.services.k8s_service import load_k8s_client_from_content
        load_k8s_client_from_content(data.kubeconfig_content)
    except Exception as e:
        logger.warning(f"更新 kubeconfig 失败: 集群 id={cluster_id}, 原因: kubeconfig 无效")
        raise HTTPException(status_code=400, detail=f"kubeconfig 无效: {str(e)}")

    # 加密并保存新的 kubeconfig
    cluster.kubeconfig_encrypted = encrypt_kubeconfig(data.kubeconfig_content)
    await db.commit()
    await db.refresh(cluster)
    logger.info(f"Kubeconfig 更新成功: 集群 id={cluster_id}, name={cluster.name}")
    return cluster


@router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """删除集群"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"删除集群失败: id={cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    cluster_name = cluster.name
    await db.delete(cluster)
    await db.commit()
    logger.info(f"集群已删除: id={cluster_id}, name={cluster_name}")
    return {"message": "删除成功"}


@router.get("/{cluster_id}/test")
async def test_cluster_connection(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """测试集群连接"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        logger.warning(f"测试连接失败: 集群 id={cluster_id} 不存在")
        raise HTTPException(status_code=404, detail="集群不存在")

    try:
        api_client = get_api_client_for_cluster(cluster)
        v1 = client.CoreV1Api(api_client)
        v1.list_namespace()
        logger.info(f"集群连接测试成功: id={cluster_id}, name={cluster.name}")
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        logger.warning(f"集群连接测试失败: id={cluster_id}, 原因: {str(e)}")
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")
