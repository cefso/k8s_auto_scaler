"""
审计日志 API

提供：
- GET /api/audit/logs - 获取审计日志列表
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


async def create_audit_log(
    action: str,
    resource_type: str,
    resource_name: str,
    namespace: str = None,
    cluster_id: int = None,
    details: dict = None,
    operator: str = "admin",
) -> None:
    """创建审计日志记录

    这是一个独立函数，可在任何地方调用来记录审计日志。
    """
    async with AsyncSessionLocal() as db:
        try:
            log = AuditLog(
                operator=operator,
                action=action,
                resource_type=resource_type,
                resource_name=resource_name,
                namespace=namespace,
                cluster_id=cluster_id,
                details=json.dumps(details) if details else None,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            logger.error(f"创建审计日志失败: {e}")
            # 审计日志失败不应该影响主业务，所以静默处理


@router.get("/logs")
async def get_audit_logs(
    cluster_id: int | None = Query(None, description="集群 ID 过滤（可选）"),
    action: str | None = Query(None, description="操作类型过滤（可选）"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志列表

    支持按集群 ID 和操作类型过滤。
    """
    filters = []
    if cluster_id is not None:
        filters.append(AuditLog.cluster_id == cluster_id)
    if action is not None:
        filters.append(AuditLog.action == action)

    query = select(AuditLog).where(*filters).order_by(desc(AuditLog.timestamp))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    count_query = select(func.count(AuditLog.id)).where(*filters)
    total = await db.scalar(count_query) or 0

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "operator": log.operator,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_name": log.resource_name,
            "namespace": log.namespace,
            "cluster_id": log.cluster_id,
            "details": json.loads(log.details) if log.details else None,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}
