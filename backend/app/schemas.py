"""
Pydantic 请求/响应模型

用于 API 入参校验与返回序列化，与 SQLAlchemy models 分离。
"""
from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Cluster ----------
class ClusterBase(BaseModel):
    name: str
    display_name: str | None = None


class ClusterCreate(ClusterBase):
    kubeconfig_content: str  # 用户上传的 kubeconfig 内容


class ClusterUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None


class ClusterResponse(ClusterBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Scaling Schedule ----------
class ScalingScheduleBase(BaseModel):
    cluster_id: int
    namespace: str
    resource_type: str = "Deployment"
    resource_name: str
    target_replicas: int = Field(ge=0)
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    description: str | None = None
    is_enabled: bool = True


class ScalingScheduleCreate(ScalingScheduleBase):
    pass


class ScalingScheduleUpdate(BaseModel):
    target_replicas: int | None = Field(None, ge=0)
    cron_expression: str | None = None
    timezone: str | None = None
    description: str | None = None
    is_enabled: bool | None = None


class ScalingScheduleResponse(ScalingScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- K8s 资源 ----------
class K8sResourceBase(BaseModel):
    name: str
    namespace: str
    kind: str
    replicas: int | None = None
    ready_replicas: int | None = None
    status: str | None = None
    age: str | None = None
    labels: dict | None = None
    annotations: dict | None = None


class K8sResourceResponse(K8sResourceBase):
    pass


class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: str
    restarts: int
    age: str
    node: str | None = None
    ip: str | None = None


class ResourceListResponse(BaseModel):
    cluster_id: int
    resource_type: str
    items: list
    total: int


class ScaleRequest(BaseModel):
    namespace: str
    resource_type: str  # Deployment, StatefulSet
    resource_name: str
    replicas: int
