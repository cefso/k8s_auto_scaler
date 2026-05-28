"""
Kubernetes Pod 日志 API

提供：
- GET /logs/{cluster_id}/pod - 获取 Pod 历史日志
- WebSocket /ws/logs/{cluster_id}/pod - 流式获取 Pod 实时日志
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_user, get_user_from_token
from app.database import get_db, AsyncSessionLocal
from app.models import Cluster
from app.services.k8s_service import get_api_client_for_cluster
from app.services.log_service import (
    get_pod_logs,
    stream_pod_logs,
    get_pod_containers,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])


async def _get_cluster(db: AsyncSession, cluster_id: int) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="集群已禁用")
    return cluster


@router.get("/{cluster_id}/pod")
async def get_pod_logs_endpoint(
    cluster_id: int,
    namespace: str = Query(..., description="命名空间"),
    pod_name: str = Query(..., description="Pod 名称"),
    container: Optional[str] = Query(None, description="容器名称（可选，默认第一个容器）"),
    tail_lines: int = Query(500, description="返回最近 N 行日志", ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    """获取 Pod 的历史日志（非流式）"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    logs = await get_pod_logs(
        api_client=api_client,
        namespace=namespace,
        pod_name=pod_name,
        container_name=container,
        tail_lines=tail_lines,
    )

    return {
        "cluster_id": cluster_id,
        "namespace": namespace,
        "pod_name": pod_name,
        "container": container,
        "logs": logs,
    }


@router.get("/{cluster_id}/pod/containers")
async def get_pod_containers_endpoint(
    cluster_id: int,
    namespace: str = Query(..., description="命名空间"),
    pod_name: str = Query(..., description="Pod 名称"),
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    """获取 Pod 的所有容器信息"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    containers = get_pod_containers(
        api_client=api_client,
        namespace=namespace,
        pod_name=pod_name,
    )

    return {
        "cluster_id": cluster_id,
        "namespace": namespace,
        "pod_name": pod_name,
        "containers": containers,
    }


@router.websocket("/ws/{cluster_id}/pod")
async def websocket_pod_logs(
    websocket: WebSocket,
    cluster_id: int,
    namespace: str,
    pod_name: str,
    container: Optional[str] = None,
    tail_lines: int = 100,
    access_token: Optional[str] = None,
):
    """WebSocket 流式获取 Pod 实时日志

    连接格式: ws://host/api/logs/ws/{cluster_id}/pod?namespace=xxx&pod_name=xxx&container=xxx&tail_lines=100

    消息格式:
    - 日志行: {"type": "log", "content": "..."}
    - 错误: {"type": "error", "content": "..."}
    - 完成: {"type": "done"}
    """
    token = access_token
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        user = await get_user_from_token(token or "", db)
        if not user:
            await websocket.close(code=4401, reason="未登录或凭证无效")
            return

        result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
        cluster = result.scalar_one_or_none()
        if not cluster:
            await websocket.close(code=4004, reason="集群不存在")
            return
        if not cluster.is_active:
            await websocket.close(code=4003, reason="集群已禁用")
            return

    try:
        api_client = get_api_client_for_cluster(cluster)
    except Exception as e:
        logger.error("创建 API 客户端失败: %s", e)
        await websocket.send_json({"type": "error", "content": f"集群配置错误: {e}"})
        await websocket.close(code=4001, reason="集群配置错误")
        return

    # 创建异步迭代器来流式获取日志
    async def log_generator():
        try:
            async for line in stream_pod_logs(
                api_client=api_client,
                namespace=namespace,
                pod_name=pod_name,
                container_name=container,
                tail_lines=tail_lines,
            ):
                yield line
        except Exception as e:
            logger.error(f"日志流异常: {e}")
            yield f"error:日志流异常: {str(e)}"

    try:
        # 持续发送日志直到客户端断开
        async for line in log_generator():
            if line.startswith("error:"):
                await websocket.send_json({
                    "type": "error",
                    "content": line[5:],  # 去掉 "error:" 前缀
                })
            elif line.startswith("log:"):
                await websocket.send_json({
                    "type": "log",
                    "content": line[4:],  # 去掉 "log:" 前缀
                })
            else:
                await websocket.send_json({
                    "type": "log",
                    "content": line,
                })

        # 发送完成信号
        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket 日志连接断开: cluster={cluster_id}, pod={namespace}/{pod_name}")
    except Exception as e:
        logger.error(f"WebSocket 日志传输异常: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"传输异常: {str(e)}",
            })
        except:
            pass
