"""
Kubernetes 资源分析与健康度评估服务

提供：
- Deployment/StatefulSet 资源健康度分析
- 浪费资源检测
- OOMKilled/限流风险检测
"""
import logging
from typing import Optional

from kubernetes import client
from kubernetes.client.rest import ApiException

from app.services.k8s_service import _pod_metrics_by_name_in_namespace

logger = logging.getLogger(__name__)


def parse_cpu_value(value: str) -> float:
    """解析 Kubernetes CPU 资源值为 cores"""
    if not value:
        return 0.0
    if value.endswith("m"):
        return int(value[:-1]) / 1000
    elif value.endswith("n"):
        return int(value[:-1]) / 1_000_000_000
    else:
        try:
            return float(value)
        except ValueError:
            return 0.0


def parse_memory_value(value: str) -> int:
    """解析 Kubernetes 内存资源值（bytes）"""
    if not value:
        return 0
    if value.endswith("Ki"):
        return int(value[:-2]) * 1024
    elif value.endswith("Mi"):
        return int(value[:-2]) * 1024 * 1024
    elif value.endswith("Gi"):
        return int(value[:-2]) * 1024 * 1024 * 1024
    elif value.endswith("Ti"):
        return int(value[:-2]) * 1024 * 1024 * 1024 * 1024
    elif value.endswith("K") and not value.endswith("Ki"):
        return int(value[:-1]) * 1000
    elif value.endswith("M") and not value.endswith("Mi"):
        return int(value[:-1]) * 1000 * 1000
    elif value.endswith("G") and not value.endswith("Gi"):
        return int(value[:-1]) * 1000 * 1000 * 1000
    elif value.endswith("T") and not value.endswith("Ti"):
        return int(value[:-1]) * 1000 * 1000 * 1000 * 1000
    else:
        try:
            return int(value)
        except ValueError:
            return 0


def analyze_workload_health(
    api_client: client.ApiClient,
    namespace: Optional[str] = None,
) -> list[dict]:
    """分析 Deployment/StatefulSet 的资源健康度

    Args:
        api_client: K8s API client
        namespace: 命名空间过滤（可选）

    Returns:
        工作负载健康度列表，每项包含：
        - name, namespace, kind: 基本信息
        - cpu_request, cpu_limit, memory_request, memory_limit: 资源配置
        - cpu_usage, memory_usage: 实际使用量
        - health_status: healthy / warning / waste
        - health_reason: 健康原因
        - suggestions: 优化建议列表
    """
    apps_v1 = client.AppsV1Api(api_client)
    v1 = client.CoreV1Api(api_client)

    workloads = []

    # 获取 Deployments
    if namespace:
        deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
        statefulsets = apps_v1.list_namespaced_stateful_set(namespace=namespace)
    else:
        deployments = apps_v1.list_deployment_for_all_namespaces()
        statefulsets = apps_v1.list_stateful_set_for_all_namespaces()

    # 分析每个 Deployment
    for d in deployments.items:
        analysis = _analyze_deployment_or_statefulset(
            d, "Deployment", v1, api_client
        )
        if analysis:
            workloads.append(analysis)

    # 分析每个 StatefulSet
    for s in statefulsets.items:
        analysis = _analyze_deployment_or_statefulset(
            s, "StatefulSet", v1, api_client
        )
        if analysis:
            workloads.append(analysis)

    return workloads


def _analyze_deployment_or_statefulset(
    obj,
    kind: str,
    v1: client.CoreV1Api,
    api_client: client.ApiClient,
) -> Optional[dict]:
    """分析单个 Deployment 或 StatefulSet 的健康度"""
    namespace = obj.metadata.namespace
    name = obj.metadata.name

    # 获取资源限制
    cpu_request = 0.0
    cpu_limit = 0.0
    memory_request = 0
    memory_limit = 0

    for container in obj.spec.template.spec.containers:
        if container.resources:
            # Requests
            if container.resources.requests:
                cpu_req = container.resources.requests.get("cpu")
                mem_req = container.resources.requests.get("memory")
                if cpu_req:
                    cpu_request += parse_cpu_value(str(cpu_req))
                if mem_req:
                    memory_request += parse_memory_value(str(mem_req))

            # Limits
            if container.resources.limits:
                cpu_lim = container.resources.limits.get("cpu")
                mem_lim = container.resources.limits.get("memory")
                if cpu_lim:
                    cpu_limit += parse_cpu_value(str(cpu_lim))
                if mem_lim:
                    memory_limit += parse_memory_value(str(mem_lim))

    # 获取实际使用量
    cpu_usage, memory_usage = _get_workload_usage(
        v1, namespace, name, kind, api_client
    )

    # 计算健康度
    health_status, health_reason, suggestions = _calculate_health(
        cpu_limit, cpu_usage, memory_limit, memory_usage
    )

    return {
        "name": name,
        "namespace": namespace,
        "kind": kind,
        "replicas": obj.spec.replicas or 0,
        "ready_replicas": getattr(obj.status, "ready_replicas", None) or 0,
        "cpu_request": round(cpu_request, 4),
        "cpu_limit": round(cpu_limit, 4),
        "memory_request": memory_request,
        "memory_limit": memory_limit,
        "cpu_usage": round(cpu_usage, 4) if cpu_usage else None,
        "memory_usage": memory_usage,
        "health_status": health_status,
        "health_reason": health_reason,
        "suggestions": suggestions,
    }


def _get_workload_usage(
    v1: client.CoreV1Api,
    namespace: str,
    workload_name: str,
    workload_kind: str,
    api_client: client.ApiClient,
) -> tuple[float, int]:
    """获取工作负载的实际资源使用量

    Returns:
        (cpu_usage_cores, memory_usage_bytes)
    """
    cpu_usage = 0.0
    memory_usage = 0

    # 获取该工作负载的 Pods
    label_selector = None
    if workload_kind == "Deployment":
        if obj_spec := getattr(
            v1, "read_namespaced_deployment", None
        ):
            try:
                deploy = v1.read_namespaced_deployment(workload_name, namespace)
                if deploy.spec.selector and deploy.spec.selector.match_labels:
                    label_selector = ",".join(
                        f"{k}={v}"
                        for k, v in deploy.spec.selector.match_labels.items()
                    )
            except Exception:
                pass
    elif workload_kind == "StatefulSet":
        try:
            sts = v1.read_namespaced_stateful_set(workload_name, namespace)
            if sts.spec.selector and sts.spec.selector.match_labels:
                label_selector = ",".join(
                    f"{k}={v}"
                    for k, v in sts.spec.selector.match_labels.items()
                )
        except Exception:
            pass

    if not label_selector:
        return cpu_usage, memory_usage

    try:
        pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        pod_metrics = _pod_metrics_by_name_in_namespace(api_client, namespace)
        for pod in pods.items:
            metrics = pod_metrics.get(pod.metadata.name)
            if metrics:
                cpu_usage += metrics.get("cpu_usage", 0)
                memory_usage += metrics.get("memory_usage", 0)
    except Exception as e:
        logger.warning(f"获取 Pod 列表失败: {e}")

    return cpu_usage, memory_usage


def _calculate_health(
    cpu_limit: float,
    cpu_usage: float,
    memory_limit: int,
    memory_usage: int,
) -> tuple[str, str, list[str]]:
    """计算资源健康度

    Args:
        cpu_limit, cpu_usage: CPU 限制和实际使用量（cores）
        memory_limit, memory_usage: 内存限制和实际使用量（bytes）

    Returns:
        (health_status, health_reason, suggestions)
    """
    health_status = "healthy"
    health_reason = "资源配置合理"
    suggestions = []

    # 检查 CPU
    if cpu_limit > 0 and cpu_usage is not None:
        cpu_usage_ratio = cpu_usage / cpu_limit if cpu_limit > 0 else 0

        # 风险检测：使用量超过 85% 限制
        if cpu_usage_ratio > 0.85:
            health_status = "warning"
            health_reason = "存在限流风险"
            suggestions.append(
                f"CPU 使用率已达 {cpu_usage_ratio * 100:.1f}%，建议增加 CPU Limit 或优化应用"
            )

        # 浪费检测：Limit 是使用量的 5 倍以上
        if cpu_limit > 0 and cpu_usage > 0 and cpu_limit / cpu_usage > 5:
            health_status = "waste"
            health_reason = "存在资源浪费"
            suggestions.append(
                f"CPU Limit ({cpu_limit:.2f}C) 是实际使用量 ({cpu_usage:.2f}C) 的 "
                f"{cpu_limit / cpu_usage:.1f} 倍，建议降低 CPU Limit"
            )

    # 检查内存
    if memory_limit > 0 and memory_usage is not None:
        memory_usage_ratio = memory_usage / memory_limit if memory_limit > 0 else 0

        # 风险检测：使用量超过 85% 限制
        if memory_usage_ratio > 0.85:
            if health_status != "waste":  # 浪费比风险更严重
                health_status = "warning"
                health_reason = "存在 OOM 风险"
            suggestions.append(
                f"内存使用率已达 {memory_usage_ratio * 100:.1f}%，建议增加内存 Limit 或优化应用"
            )

        # 浪费检测：Limit 是使用量的 5 倍以上
        if memory_limit > 0 and memory_usage > 0 and memory_limit / memory_usage > 5:
            health_status = "waste"
            health_reason = "存在资源浪费"
            suggestions.append(
                f"内存 Limit ({_format_bytes(memory_limit)}) 是实际使用量 ({_format_bytes(memory_usage)}) 的 "
                f"{memory_limit / memory_usage:.1f} 倍，建议降低内存 Limit"
            )

    # 如果都没有问题，设置为 healthy
    if health_status == "healthy" and not suggestions:
        suggestions.append("资源配置合理，无需调整")

    return health_status, health_reason, suggestions


def _format_bytes(bytes_val: int) -> str:
    """格式化字节数为可读字符串"""
    if bytes_val == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(bytes_val)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.2f}{units[i]}"
