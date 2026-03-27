"""
Kubernetes 集群服务

- 从数据库解密 kubeconfig 并创建 K8s API 客户端
- 封装各类资源（Deployment、Pod、Service 等）的列表与扩缩容操作
- 支持 CRD：Argo Rollout、Apache APISIX Route/TLS、Traefik IngressRoute/TCP/UDP、Helm Release
"""
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Cluster
from app.crypto_utils import decrypt_kubeconfig

logger = logging.getLogger(__name__)


def load_k8s_client_from_content(kubeconfig_content: str):
    """从 kubeconfig YAML 字符串创建 Kubernetes ApiClient，用于多集群并发访问。"""
    try:
        config_dict = yaml.safe_load(kubeconfig_content)
        if not config_dict:
            raise ValueError("kubeconfig 内容为空")
        return config.new_client_from_config_dict(config_dict)
    except Exception as e:
        raise ValueError(f"无法加载 kubeconfig: {str(e)}")


def get_api_client_for_cluster(cluster: Cluster):
    """根据 Cluster 模型解密 kubeconfig 并返回该集群的 K8s ApiClient。"""
    content = decrypt_kubeconfig(cluster.kubeconfig_encrypted)
    return load_k8s_client_from_content(content)


def get_kubeconfig_content_for_cluster(cluster: Cluster) -> str:
    """解密并返回集群的 kubeconfig 内容。"""
    return decrypt_kubeconfig(cluster.kubeconfig_encrypted)


async def get_cluster_by_id(db: AsyncSession, cluster_id: int) -> Cluster | None:
    """根据 ID 获取集群"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    return result.scalar_one_or_none()


def list_namespaces(api_client) -> list[dict]:
    """列出所有命名空间"""
    v1 = client.CoreV1Api(api_client)
    namespaces = v1.list_namespace()
    return [
        {
            "name": ns.metadata.name,
            "status": ns.status.phase if ns.status else "Unknown",
            "age": _get_age(ns.metadata.creation_timestamp),
        }
        for ns in namespaces.items
    ]


def list_deployments(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Deployments"""
    apps_v1 = client.AppsV1Api(api_client)
    if namespace:
        deploys = apps_v1.list_namespaced_deployment(namespace=namespace)
    else:
        deploys = apps_v1.list_deployment_for_all_namespaces()
    
    return [
        {
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "replicas": d.spec.replicas or 0,
            "ready_replicas": d.status.ready_replicas or 0,
            "status": _deployment_status(d),
            "age": _get_age(d.metadata.creation_timestamp),
            "labels": dict(d.metadata.labels) if d.metadata.labels else {},
        }
        for d in deploys.items
    ]


def list_rollouts(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Argo Rollout 资源 (argoproj.io)"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="rollouts",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="rollouts",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        status = r.get("status", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        replicas = spec.get("replicas", 0)
        ready = status.get("readyReplicas", 0) or status.get("availableReplicas", 0)
        phase = status.get("phase", "-") or status.get("message", "-")
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "replicas": replicas,
            "ready_replicas": ready,
            "status": phase if phase else ("Ready" if ready == replicas and replicas else "Progressing"),
            "age": _get_age(created) if created else "-",
        })
    return out


def list_statefulsets(api_client, namespace: str | None = None) -> list[dict]:
    """列出 StatefulSets"""
    apps_v1 = client.AppsV1Api(api_client)
    if namespace:
        sts_list = apps_v1.list_namespaced_stateful_set(namespace=namespace)
    else:
        sts_list = apps_v1.list_stateful_set_for_all_namespaces()
    
    return [
        {
            "name": s.metadata.name,
            "namespace": s.metadata.namespace,
            "replicas": s.spec.replicas or 0,
            "ready_replicas": s.status.ready_replicas or 0,
            "status": _statefulset_status(s),
            "age": _get_age(s.metadata.creation_timestamp),
            "labels": dict(s.metadata.labels) if s.metadata.labels else {},
        }
        for s in sts_list.items
    ]


def list_services(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Services"""
    v1 = client.CoreV1Api(api_client)
    if namespace:
        svcs = v1.list_namespaced_service(namespace=namespace)
    else:
        svcs = v1.list_service_for_all_namespaces()
    return [
        {
            "name": s.metadata.name,
            "namespace": s.metadata.namespace,
            "type": s.spec.type if s.spec else "ClusterIP",
            "cluster_ip": s.spec.cluster_ip if s.spec else "-",
            "ports": _format_ports(s.spec.ports) if s.spec and s.spec.ports else [],
            "age": _get_age(s.metadata.creation_timestamp),
        }
        for s in svcs.items
    ]


def list_apisixroutes(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Apache APISIX Route 资源"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="apisix.apache.org",
                version="v2",
                namespace=namespace,
                plural="apisixroutes",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="apisix.apache.org",
                version="v2",
                plural="apisixroutes",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        hosts = _get_apisix_route_hosts(spec)
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "hosts": hosts,
            "age": _get_age(created) if created else "-",
        })
    return out


def list_apisixtlses(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Apache APISIX TLS 资源"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="apisix.apache.org",
                version="v2",
                namespace=namespace,
                plural="apisixtlses",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="apisix.apache.org",
                version="v2",
                plural="apisixtlses",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        hosts = ", ".join(spec.get("hosts", [])) if spec.get("hosts") else "-"
        secret = spec.get("secret", {})
        secret_ref = f"{secret.get('namespace', ns)}/{secret.get('name', '-')}" if isinstance(secret, dict) else "-"
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "hosts": hosts,
            "secret": secret_ref,
            "age": _get_age(created) if created else "-",
        })
    return out


def _get_apisix_route_hosts(spec: dict) -> str:
    """从 ApisixRoute spec 提取 hosts"""
    http = spec.get("http", [])
    hosts = set()
    for h in http:
        match = h.get("match", {})
        for host in match.get("hosts", []):
            hosts.add(host)
    return ", ".join(hosts) if hosts else "-"


def list_traefikingresses(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Traefik IngressRoute 资源"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="traefik.io",
                version="v1alpha1",
                namespace=namespace,
                plural="ingressroutes",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="traefik.io",
                version="v1alpha1",
                plural="ingressroutes",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        hosts = _get_traefik_hosts(spec)
        entry_points = ", ".join(spec.get("entryPoints", [])) if spec.get("entryPoints") else "-"
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "hosts": hosts,
            "entry_points": entry_points,
            "age": _get_age(created) if created else "-",
        })
    return out


def list_traefikingresstcps(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Traefik IngressRouteTCP 资源"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="traefik.io",
                version="v1alpha1",
                namespace=namespace,
                plural="ingressroutetcps",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="traefik.io",
                version="v1alpha1",
                plural="ingressroutetcps",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        entry_points = ", ".join(spec.get("entryPoints", [])) if spec.get("entryPoints") else "-"
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "entry_points": entry_points,
            "age": _get_age(created) if created else "-",
        })
    return out


def list_traefikingressudps(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Traefik IngressRouteUDP 资源"""
    custom_api = client.CustomObjectsApi(api_client)
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group="traefik.io",
                version="v1alpha1",
                namespace=namespace,
                plural="ingressrouteudps",
            )
        else:
            result = custom_api.list_cluster_custom_object(
                group="traefik.io",
                version="v1alpha1",
                plural="ingressrouteudps",
            )
    except ApiException as e:
        if e.status == 404:
            return []
        raise

    items = result.get("items", [])
    out = []
    for r in items:
        meta = r.get("metadata", {})
        spec = r.get("spec", {})
        ns = meta.get("namespace", "")
        name = meta.get("name", "")
        entry_points = ", ".join(spec.get("entryPoints", [])) if spec.get("entryPoints") else "-"
        created = meta.get("creationTimestamp")
        out.append({
            "name": name,
            "namespace": ns,
            "entry_points": entry_points,
            "age": _get_age(created) if created else "-",
        })
    return out


def _get_traefik_hosts(spec: dict) -> str:
    """从 Traefik IngressRoute spec 提取 hosts"""
    routes = spec.get("routes", [])
    hosts = set()
    for route in routes:
        match = route.get("match", "")
        m = re.search(r"Host\(`([^`]+)`\)", match)
        if m:
            hosts.add(m.group(1))
    return ", ".join(hosts) if hosts else "-"


def list_ingresses(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Ingresses"""
    net_v1 = client.NetworkingV1Api(api_client)
    if namespace:
        ings = net_v1.list_namespaced_ingress(namespace=namespace)
    else:
        ings = net_v1.list_ingress_for_all_namespaces()
    return [
        {
            "name": ing.metadata.name,
            "namespace": ing.metadata.namespace,
            "hosts": _get_ingress_hosts(ing),
            "class_name": getattr(ing.spec, 'ingress_class_name', '-') if ing.spec else "-",
            "tls": _get_ingress_tls(ing),
            "age": _get_age(ing.metadata.creation_timestamp),
        }
        for ing in ings.items
    ]


def _format_ports(ports) -> str:
    """格式化端口信息"""
    if not ports:
        return "-"
    parts = []
    for p in ports:
        if p.node_port:
            parts.append(f"{p.port}/{p.protocol or 'TCP'}:{p.node_port}")
        else:
            parts.append(f"{p.port}/{p.protocol or 'TCP'}")
    return ", ".join(parts)


def _get_ingress_hosts(ing) -> str:
    """获取 Ingress 的 hosts"""
    if not ing.spec or not ing.spec.rules:
        return "-"
    hosts = [r.host for r in ing.spec.rules if r.host]
    return ", ".join(hosts) if hosts else "-"


def _get_ingress_tls(ing) -> str:
    """获取 Ingress 的 TLS secret 名称"""
    if not ing.spec or not ing.spec.tls:
        return "-"
    secrets = []
    for tls in ing.spec.tls:
        if tls.secret_name:
            secrets.append(tls.secret_name)
    return ", ".join(secrets) if secrets else "-"


def list_helm_releases(kubeconfig_content: str, namespace: str | None = None) -> dict:
    """列出 Helm 应用 (通过 helm list 命令)

    返回格式:
    - helm_available=True: {"items": [...], "helm_available": True, "error": None}
    - helm_available=False: {"items": [], "helm_available": False, "error": "helm 未安装或下载失败"}
    """
    helm_path = _ensure_helm()
    if not helm_path:
        logger.warning("helm not available, 请确保 helm CLI 已安装并可访问")
        return {"items": [], "helm_available": False, "error": "helm 未安装或下载失败，请确保 helm CLI 已安装并可访问"}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
        f.write(kubeconfig_content)
        kubeconfig_path = f.name

    try:
        cmd = [helm_path, "list", "-A", "-o", "json"]
        if namespace:
            cmd = [helm_path, "list", "-n", namespace, "-o", "json"]
        env = os.environ.copy()
        env["KUBECONFIG"] = kubeconfig_path
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        if result.returncode != 0:
            logger.warning(f"helm list failed: {result.stderr}")
            return {"items": [], "helm_available": True, "error": None}
        releases = json.loads(result.stdout)
        out = []
        for r in releases:
            last_deployed = r.get("last_deployed", "")
            age = _parse_helm_age(last_deployed) if last_deployed else "-"
            out.append({
                "name": r.get("name", ""),
                "namespace": r.get("namespace", ""),
                "revision": r.get("revision", ""),
                "status": r.get("status", ""),
                "chart": r.get("chart", ""),
                "app_version": r.get("app_version", ""),
                "age": age,
            })
        return {"items": out, "helm_available": True, "error": None}
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"helm list error: {e}")
        return {"items": [], "helm_available": True, "error": None}
    finally:
        os.unlink(kubeconfig_path)


def _ensure_helm() -> str | None:
    """检测或安装 helm CLI，返回 helm 路径"""
    # 1. 检查 PATH 中是否已有 helm
    helm_in_path = _find_helm_in_path()
    if helm_in_path:
        return helm_in_path

    # 2. 检查 ~/.local/bin/helm 或项目内的 helm
    local_helm = os.path.expanduser("~/.local/bin/helm")
    if os.path.isfile(local_helm) and os.access(local_helm, os.X_OK):
        return local_helm

    # 3. 自动下载 helm
    helm_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bin")
    os.makedirs(helm_dir, exist_ok=True)
    helm_path = os.path.join(helm_dir, "helm")

    if os.path.isfile(helm_path) and os.access(helm_path, os.X_OK):
        return helm_path

    logger.info("helm not found, attempting to download...")

    # 检测平台
    platform = _get_platform()
    if not platform:
        logger.error(" unsupported platform for helm download")
        return None

    url = f"https://get.helm.sh/helm-{_HELM_VERSION}-{platform}.tar.gz"

    try:
        import urllib.request
        import tarfile
        import zipfile  # noqa: F401

        # 下载
        tar_path = tempfile.mktemp(suffix=".tar.gz")
        urllib.request.urlretrieve(url, tar_path)

        # 解压
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("/helm") or member.name == "helm":
                    member.name = "helm"
                    tar.extract(member, helm_dir)

        os.unlink(tar_path)
        os.chmod(helm_path, 0o755)
        logger.info(f"helm installed to {helm_path}")
        return helm_path
    except Exception as e:
        logger.error(f"failed to download helm: {e}")
        # 清理失败的文件
        if os.path.exists(helm_path):
            os.remove(helm_path)
        return None


def _find_helm_in_path() -> str | None:
    """在 PATH 中查找 helm"""
    for dir in os.environ.get("PATH", "").split(os.pathsep):
        path = os.path.join(dir, "helm")
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _get_platform() -> str | None:
    """获取当前平台的 helm 下载标识"""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Linux
    if system == "linux":
        if machine == "x86_64":
            return "linux-amd64"
        elif machine == "aarch64" or machine == "arm64":
            return "linux-arm64"
    # macOS
    elif system == "darwin":
        if machine == "x86_64":
            return "darwin-amd64"
        elif machine == "aarch64" or machine == "arm64":
            return "darwin-arm64"
    return None


_HELM_VERSION = "v3.16.3"


def _parse_helm_age(last_deployed: str) -> str:
    """解析 helm last_deployed 时间戳为年龄字符串"""
    if not last_deployed:
        return "-"
    try:
        # helm 输出格式: "2024-01-15 10:30:00.000000000 +0800 CST"
        dt = datetime.strptime(last_deployed.split(".")[0], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "<1m"
    except (ValueError, TypeError):
        return "-"


def list_configmaps(api_client, namespace: str | None = None) -> list[dict]:
    """列出 ConfigMaps"""
    v1 = client.CoreV1Api(api_client)
    if namespace:
        cms = v1.list_namespaced_config_map(namespace=namespace)
    else:
        cms = v1.list_config_map_for_all_namespaces()
    return [
        {
            "name": cm.metadata.name,
            "namespace": cm.metadata.namespace,
            "data_keys": list(cm.data) if cm.data else [],
            "age": _get_age(cm.metadata.creation_timestamp),
        }
        for cm in cms.items
    ]


def list_secrets(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Secrets"""
    v1 = client.CoreV1Api(api_client)
    if namespace:
        secrets = v1.list_namespaced_secret(namespace=namespace)
    else:
        secrets = v1.list_secret_for_all_namespaces()
    return [
        {
            "name": s.metadata.name,
            "namespace": s.metadata.namespace,
            "type": s.type or "Opaque",
            "data_keys": list(s.data) if s.data else [],
            "age": _get_age(s.metadata.creation_timestamp),
        }
        for s in secrets.items
    ]


def list_pods(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Pods"""
    v1 = client.CoreV1Api(api_client)
    if namespace:
        pods = v1.list_namespaced_pod(namespace=namespace)
    else:
        pods = v1.list_pod_for_all_namespaces()
    
    result = []
    for p in pods.items:
        status = "Unknown"
        if p.status:
            if p.status.phase:
                status = p.status.phase
            elif p.status.container_statuses:
                cs = p.status.container_statuses[0]
                status = "Running" if cs.ready else "NotReady"
        ready = "0/0"
        restarts = 0
        if p.status and p.status.container_statuses:
            total = len(p.status.container_statuses)
            r = sum(1 for c in p.status.container_statuses if c.ready)
            ready = f"{r}/{total}"
            restarts = sum(c.restart_count for c in p.status.container_statuses)
        
        result.append({
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "status": status,
            "ready": ready,
            "restarts": restarts,
            "age": _get_age(p.metadata.creation_timestamp),
            "node": p.spec.node_name if p.spec else None,
            "ip": p.status.pod_ip if p.status else None,
        })
    return result


def get_cluster_metrics(api_client, kubeconfig_content: str = None) -> dict:
    """获取集群 metrics 汇总信息

    返回:
    - pod_stats: Pod 统计（总数、running、pending、failed）
    - node_count: 节点数量
    - deployment_count: Deployment 数量
    - statefulset_count: StatefulSet 数量
    - namespace_count: 命名空间数量
    - cpu_usage: CPU 使用量 (cores)
    - memory_usage: 内存使用量 (bytes)
    - pod_memory_request: Pod 内存请求量 (bytes)
    - pod_memory_limit: Pod 内存 limit 量 (bytes)
    - pod_cpu_request: Pod CPU 请求量 (cores)
    - pod_cpu_limit: Pod CPU limit 量 (cores)
    - metrics_available: 是否可用 metrics-server
    """
    v1 = client.CoreV1Api(api_client)
    apps_v1 = client.AppsV1Api(api_client)

    # Pod 统计及资源请求/limit 汇总
    all_pods = v1.list_pod_for_all_namespaces()
    pod_stats = {"total": 0, "running": 0, "pending": 0, "failed": 0}
    pod_memory_request = 0
    pod_memory_limit = 0
    pod_cpu_request = 0.0
    pod_cpu_limit = 0.0
    for pod in all_pods.items:
        pod_stats["total"] += 1
        phase = pod.status.phase if pod.status else "Unknown"
        if phase == "Running":
            pod_stats["running"] += 1
        elif phase == "Pending":
            pod_stats["pending"] += 1
        elif phase == "Failed":
            pod_stats["failed"] += 1
        # 统计 Pod CPU/内存请求和 limit
        for container in pod.spec.containers:
            if container.resources.requests:
                if container.resources.requests.get('cpu'):
                    pod_cpu_request += _parse_cpu_value(container.resources.requests['cpu'])
                if container.resources.requests.get('memory'):
                    pod_memory_request += _parse_resource_value(container.resources.requests['memory'])
            if container.resources.limits:
                if container.resources.limits.get('cpu'):
                    pod_cpu_limit += _parse_cpu_value(container.resources.limits['cpu'])
                if container.resources.limits.get('memory'):
                    pod_memory_limit += _parse_resource_value(container.resources.limits['memory'])

    # 节点统计
    try:
        nodes = v1.list_node()
        node_count = len(nodes.items)
    except Exception:
        node_count = 0

    # Deployment/StatefulSet 统计
    try:
        deployments = apps_v1.list_deployment_for_all_namespaces()
        deployment_count = len(deployments.items)
    except Exception:
        deployment_count = 0

    try:
        statefulsets = apps_v1.list_stateful_set_for_all_namespaces()
        statefulset_count = len(statefulsets.items)
    except Exception:
        statefulset_count = 0

    # 命名空间统计
    try:
        namespaces = v1.list_namespace()
        namespace_count = len(namespaces.items)
    except Exception:
        namespace_count = 0

    # 从 metrics-server 获取 CPU 和内存使用量（使用 kubectl top）
    cpu_usage = 0
    memory_usage = 0
    metrics_available = False
    kubeconfig_path = None

    if kubeconfig_content:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name

            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            # 获取 node metrics
            result = subprocess.run(
                ["kubectl", "top", "nodes", "--no-headers"],
                capture_output=True, text=True, env=env, timeout=30
            )
            if result.returncode == 0:
                metrics_available = True
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        # 输出格式: NAME   CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
                        if len(parts) >= 4:
                            cpu_str = parts[1]
                            mem_str = parts[3]
                            if 'm' in cpu_str:
                                cpu_usage += int(cpu_str.replace('m', '')) / 1000
                            else:
                                cpu_usage += int(cpu_str)
                            memory_usage += _parse_resource_value(mem_str)
        except Exception as e:
            logger.warning(f"无法获取 metrics: {e}")
        finally:
            if kubeconfig_path:
                os.unlink(kubeconfig_path)

    return {
        "pod_stats": pod_stats,
        "node_count": node_count,
        "deployment_count": deployment_count,
        "statefulset_count": statefulset_count,
        "namespace_count": namespace_count,
        "cpu_usage": round(cpu_usage, 2),
        "memory_usage": memory_usage,
        "pod_cpu_request": round(pod_cpu_request, 2),
        "pod_cpu_limit": round(pod_cpu_limit, 2),
        "pod_memory_request": pod_memory_request,
        "pod_memory_limit": pod_memory_limit,
        "metrics_available": metrics_available,
    }


def scale_deployment(
    api_client, namespace: str, name: str, replicas: int
) -> dict:
    """扩展 Deployment 副本数"""
    apps_v1 = client.AppsV1Api(api_client)
    try:
        apps_v1.patch_namespaced_deployment_scale(
            name=name,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        logger.info(f"Deployment 扩缩容成功: {namespace}/{name} -> {replicas} 副本")
        return {"success": True, "message": f"已将 {name} 扩缩至 {replicas} 副本"}
    except ApiException as e:
        logger.error(f"Deployment 扩缩容失败: {namespace}/{name}, 原因: {e.reason}")
        return {"success": False, "message": str(e.reason)}


def scale_statefulset(
    api_client, namespace: str, name: str, replicas: int
) -> dict:
    """扩展 StatefulSet 副本数"""
    apps_v1 = client.AppsV1Api(api_client)
    try:
        apps_v1.patch_namespaced_stateful_set_scale(
            name=name,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        logger.info(f"StatefulSet 扩缩容成功: {namespace}/{name} -> {replicas} 副本")
        return {"success": True, "message": f"已将 {name} 扩缩至 {replicas} 副本"}
    except ApiException as e:
        logger.error(f"StatefulSet 扩缩容失败: {namespace}/{name}, 原因: {e.reason}")
        return {"success": False, "message": str(e.reason)}


def _parse_cpu_value(value: str) -> float:
    """解析 Kubernetes CPU 资源值为 cores"""
    if not value:
        return 0.0
    if value.endswith("m"):
        return int(value[:-1]) / 1000  # millicores to cores
    elif value.endswith("n"):
        return int(value[:-1]) / 1_000_000_000  # nanocores to cores
    else:
        try:
            return float(value)
        except ValueError:
            return 0.0


def _parse_resource_value(value: str) -> int:
    """解析 Kubernetes 资源值（memory）"""
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


def _get_age(creation_timestamp) -> str:
    """计算资源年龄"""
    if not creation_timestamp:
        return "Unknown"
    now = datetime.now(timezone.utc)
    if isinstance(creation_timestamp, str):
        created = datetime.fromisoformat(creation_timestamp.replace("Z", "+00:00"))
    else:
        created = creation_timestamp.replace(tzinfo=timezone.utc) if creation_timestamp.tzinfo is None else creation_timestamp
    delta = now - created
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        return f"{days}d"
    elif hours > 0:
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "<1m"


def _deployment_status(d) -> str:
    """Deployment 状态"""
    if d.status.ready_replicas == d.spec.replicas and d.spec.replicas:
        return "Ready"
    if d.status.unavailable_replicas:
        return "Unavailable"
    return "Progressing"


def _statefulset_status(s) -> str:
    """StatefulSet 状态"""
    if s.status.ready_replicas == s.spec.replicas and s.spec.replicas:
        return "Ready"
    return "Updating"


def get_resource_yaml(api_client, resource_type: str, namespace: str, name: str) -> str:
    """获取资源的 YAML 表示"""
    apps_v1 = client.AppsV1Api(api_client)
    v1 = client.CoreV1Api(api_client)
    net_v1 = client.NetworkingV1Api(api_client)

    obj = None
    rt = resource_type.lower()
    if rt == "deployment":
        obj = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
    elif rt == "statefulset":
        obj = apps_v1.read_namespaced_stateful_set(name=name, namespace=namespace)
    elif rt == "pod":
        obj = v1.read_namespaced_pod(name=name, namespace=namespace)
    elif rt == "service":
        obj = v1.read_namespaced_service(name=name, namespace=namespace)
    elif rt == "ingress":
        obj = net_v1.read_namespaced_ingress(name=name, namespace=namespace)
    elif rt == "configmap":
        obj = v1.read_namespaced_config_map(name=name, namespace=namespace)
    elif rt == "secret":
        obj = v1.read_namespaced_secret(name=name, namespace=namespace)
    elif rt == "rollout":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="rollouts",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif rt == "apisixroute":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="apisix.apache.org",
            version="v2",
            namespace=namespace,
            plural="apisixroutes",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif rt == "apisixtls":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="apisix.apache.org",
            version="v2",
            namespace=namespace,
            plural="apisixtlses",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif rt == "ingressroute":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="traefik.io",
            version="v1alpha1",
            namespace=namespace,
            plural="ingressroutes",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif rt == "ingressroutetcp":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="traefik.io",
            version="v1alpha1",
            namespace=namespace,
            plural="ingressroutetcps",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif rt == "ingressrouteudp":
        custom_api = client.CustomObjectsApi(api_client)
        body = custom_api.get_namespaced_custom_object(
            group="traefik.io",
            version="v1alpha1",
            namespace=namespace,
            plural="ingressrouteudps",
            name=name,
        )
        return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        raise ValueError(f"不支持的资源类型: {resource_type}")

    body = api_client.sanitize_for_serialization(obj)
    return yaml.dump(body, default_flow_style=False, allow_unicode=True, sort_keys=False)
