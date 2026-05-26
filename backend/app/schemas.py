"""
Pydantic 请求/响应模型

用于 API 入参校验与返回序列化，与 SQLAlchemy models 分离。
"""
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator


# ---------- Auth / User ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    is_active: bool = True

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6)
    display_name: str | None = None
    role: str = "viewer"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)


# ---------- Cluster ----------
class ClusterBase(BaseModel):
    name: str
    display_name: str | None = None


class ClusterCreate(ClusterBase):
    kubeconfig_content: str  # 用户上传的 kubeconfig 内容


class ClusterUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None


class ClusterKubeconfigUpdate(BaseModel):
    kubeconfig_content: str  # 新的 kubeconfig 内容


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


def _validate_cron(expr: str, timezone: str = "Asia/Shanghai") -> str:
    try:
        CronTrigger.from_crontab(expr, timezone=timezone)
    except Exception as e:
        raise ValueError(f"无效的 Cron 表达式: {e}") from e
    return expr


class ScalingScheduleCreate(ScalingScheduleBase):
    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str, info):
        tz = info.data.get("timezone", "Asia/Shanghai")
        return _validate_cron(v, tz)


class ScalingScheduleUpdate(BaseModel):
    target_replicas: int | None = Field(None, ge=0)
    cron_expression: str | None = None
    timezone: str | None = None
    description: str | None = None
    is_enabled: bool | None = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None, info):
        if v is None:
            return v
        tz = info.data.get("timezone") or "Asia/Shanghai"
        return _validate_cron(v, tz)


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
    replicas: int = Field(ge=0)
