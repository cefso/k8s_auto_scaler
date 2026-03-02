"""
SQLAlchemy 数据库模型

- Cluster: 集群配置，kubeconfig 以 Fernet 加密存储在 kubeconfig_encrypted
- ScalingSchedule: 定时扩缩容任务，关联 Cluster
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Cluster(Base):
    """K8s 集群配置，kubeconfig 加密存储于数据库。"""
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    kubeconfig_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    scaling_schedules: Mapped[list["ScalingSchedule"]] = relationship(
        "ScalingSchedule", back_populates="cluster", cascade="all, delete-orphan"
    )


class ScalingSchedule(Base):
    """定时扩缩容任务，按 Cron 表达式在指定集群上执行 Deployment/StatefulSet 扩缩。"""
    __tablename__ = "scaling_schedules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(Integer, ForeignKey("clusters.id"), nullable=False)
    
    # 资源信息
    namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Deployment, StatefulSet
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # 目标副本数
    target_replicas: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # 定时配置 (cron 表达式: 如 "0 9 * * 1-5" 表示工作日9点)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai")
    
    # 描述
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="scaling_schedules")
