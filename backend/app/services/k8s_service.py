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


def list_hpas(api_client, namespace: str | None = None) -> list[dict]:
    """列出 HPAs (Horizontal Pod Autoscalers)"""
    autoscaling_v2 = client.AutoscalingV2Api(api_client)
    if namespace:
        hpa_list = autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(namespace=namespace)
    else:
        hpa_list = autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces()

    result = []
    for h in hpa_list.items:
        spec = h.spec
        status = h.status
        # 获取指标信息
        cpu_percent = None
        memory_percent = None
        if status and status.current_metrics:
            for metric in status.current_metrics:
                if metric.resource and metric.resource.name == "cpu":
                    cpu_percent = metric.resource.current.average_utilization
                elif metric.resource and metric.resource.name == "memory":
                    memory_percent = metric.resource.current.average_utilization

        result.append({
            "name": h.metadata.name,
            "namespace": h.metadata.namespace,
            "min_replicas": spec.min_replicas if spec else None,
            "max_replicas": spec.max_replicas if spec else None,
            "desired_replicas": status.desired_replicas if status else None,
            "current_replicas": status.current_replicas if status else None,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "age": _get_age(h.metadata.creation_timestamp),
            "labels": dict(h.metadata.labels) if h.metadata.labels else {},
        })
    return result


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


def helm_get_values(kubeconfig_content: str, namespace: str, name: str) -> dict:
    """获取 Helm release 的 values 文件

    返回格式:
    - success=True: {"values": "...", "success": True}
    - success=False: {"error": "...", "success": False}
    """
    helm_path = _ensure_helm()
    if not helm_path:
        return {"error": "helm CLI 不可用", "success": False}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
        f.write(kubeconfig_content)
        kubeconfig_path = f.name

    try:
        cmd = [helm_path, "get", "values", name, "-n", namespace]
        env = os.environ.copy()
        env["KUBECONFIG"] = kubeconfig_path
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        if result.returncode != 0:
            logger.warning(f"helm values failed: {result.stderr}")
            return {"error": result.stderr or "获取 values 失败", "success": False}
        return {"values": result.stdout, "success": True}
    except subprocess.TimeoutExpired:
        return {"error": "获取 values 超时", "success": False}
    except Exception as e:
        logger.warning(f"helm values error: {e}")
        return {"error": str(e), "success": False}
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
        logger.error("Unsupported platform for helm download")
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

        # 获取 owner_reference 信息
        owner_kind = None
        owner_name = None
        if p.metadata.owner_references:
            for ref in p.metadata.owner_references:
                if ref.kind in ['Deployment', 'StatefulSet', 'Rollout']:
                    owner_kind = ref.kind
                    owner_name = ref.name
                    break

        result.append({
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "status": status,
            "ready": ready,
            "restarts": restarts,
            "age": _get_age(p.metadata.creation_timestamp),
            "node": p.spec.node_name if p.spec else None,
            "ip": p.status.pod_ip if p.status else None,
            "owner_kind": owner_kind,
            "owner_name": owner_name,
        })
    return result


def get_workload_pods(api_client, namespace: str, workload_kind: str, workload_name: str, kubeconfig_content: str = None) -> dict:
    """获取特定工作负载的 Pod 列表及资源使用量

    Args:
        api_client: K8s API client
        namespace: 命名空间
        workload_kind: 工作负载类型 (Deployment/StatefulSet/Rollout)
        workload_name: 工作负载名称
        kubeconfig_content: kubeconfig 内容（用于获取 metrics）

    Returns:
        {"workload": {...}, "items": [...], "total": int}
    """
    v1 = client.CoreV1Api(api_client)
    apps_v1 = client.AppsV1Api(api_client)

    # 获取工作负载详情
    workload_info = None
    label_selector = None

    if workload_kind == 'Deployment':
        try:
            deploy = apps_v1.read_namespaced_deployment(name=workload_name, namespace=namespace)
            # 获取资源限制信息
            cpu_limit = 0
            memory_limit = 0
            for container in deploy.spec.template.spec.containers:
                if container.resources and container.resources.limits:
                    cpu_lim = container.resources.limits.get('cpu')
                    mem_lim = container.resources.limits.get('memory')
                    if cpu_lim:
                        cpu_limit += _parse_cpu_value(str(cpu_lim))
                    if mem_lim:
                        memory_limit += _parse_resource_value(str(mem_lim))

            workload_info = {
                "kind": "Deployment",
                "name": deploy.metadata.name,
                "namespace": deploy.metadata.namespace,
                "replicas": deploy.spec.replicas or 0,
                "ready_replicas": deploy.status.ready_replicas or 0,
                "images": list(set([c.image for c in deploy.spec.template.spec.containers])),
                "cpu_limit": round(cpu_limit, 4),
                "memory_limit": memory_limit,
            }

            if deploy.spec.selector and deploy.spec.selector.match_labels:
                labels = [f"{k}={v}" for k, v in deploy.spec.selector.match_labels.items()]
                label_selector = ",".join(labels)
        except Exception as e:
            logger.warning(f"无法获取 Deployment 详情: {e}")

    elif workload_kind == 'StatefulSet':
        try:
            sts = apps_v1.read_namespaced_stateful_set(name=workload_name, namespace=namespace)
            # 获取资源限制信息
            cpu_limit = 0
            memory_limit = 0
            for container in sts.spec.template.spec.containers:
                if container.resources and container.resources.limits:
                    cpu_lim = container.resources.limits.get('cpu')
                    mem_lim = container.resources.limits.get('memory')
                    if cpu_lim:
                        cpu_limit += _parse_cpu_value(str(cpu_lim))
                    if mem_lim:
                        memory_limit += _parse_resource_value(str(mem_lim))

            workload_info = {
                "kind": "StatefulSet",
                "name": sts.metadata.name,
                "namespace": sts.metadata.namespace,
                "replicas": sts.spec.replicas or 0,
                "ready_replicas": sts.status.ready_replicas or 0,
                "images": list(set([c.image for c in sts.spec.template.spec.containers])),
                "cpu_limit": round(cpu_limit, 4),
                "memory_limit": memory_limit,
            }

            if sts.spec.selector and sts.spec.selector.match_labels:
                labels = [f"{k}={v}" for k, v in sts.spec.selector.match_labels.items()]
                label_selector = ",".join(labels)
        except Exception as e:
            logger.warning(f"无法获取 StatefulSet 详情: {e}")

    elif workload_kind == 'Rollout':
        try:
            custom_api = client.CustomObjectsApi(api_client)
            rollout = custom_api.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="rollouts",
                name=workload_name,
            )
            spec = rollout.get("spec", {})
            status = rollout.get("status", {})
            replicas = spec.get("replicas", 0)
            ready = status.get("readyReplicas", 0) or status.get("availableReplicas", 0)

            # 获取镜像
            images = []
            template_spec = spec.get("template", {}).get("spec", {})
            for container in template_spec.get("containers", []):
                if container.get("image"):
                    images.append(container["image"])

            workload_info = {
                "kind": "Rollout",
                "name": rollout.get("metadata", {}).get("name"),
                "namespace": rollout.get("metadata", {}).get("namespace"),
                "replicas": replicas,
                "ready_replicas": ready,
                "images": list(set(images)),
                "cpu_limit": None,
                "memory_limit": None,
            }

            selector = spec.get("selector", {})
            match_labels = selector.get("matchLabels", {})
            if match_labels:
                labels = [f"{k}={v}" for k, v in match_labels.items()]
                label_selector = ",".join(labels)
        except Exception as e:
            logger.warning(f"无法获取 Rollout 详情: {e}")

    # 使用 label selector 过滤 Pod
    if label_selector:
        pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        filtered_pods = list(pods.items)
    else:
        # 降级方案：使用 owner_reference
        controller_name = workload_name
        if workload_kind == 'Deployment':
            try:
                rs_list = apps_v1.list_namespaced_replica_set(namespace=namespace)
                for rs in rs_list.items:
                    if rs.metadata.owner_references:
                        for ref in rs.metadata.owner_references:
                            if ref.kind == 'Deployment' and ref.name == workload_name:
                                controller_name = rs.metadata.name
                                break
            except Exception:
                pass

        pods = v1.list_namespaced_pod(namespace=namespace)
        filtered_pods = []
        target_kinds = ['ReplicaSet'] if workload_kind == 'Deployment' else [workload_kind]

        for pod in pods.items:
            if not pod.metadata.owner_references:
                continue
            for ref in pod.metadata.owner_references:
                if ref.kind in target_kinds and ref.name == controller_name:
                    filtered_pods.append(pod)
                    break

    # 构建返回数据（包含资源信息）
    items = []
    pod_metrics_map = {}

    # 通过 kubectl top pods 获取实际使用量
    if kubeconfig_content:
        kubeconfig_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name

            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            result = subprocess.run(
                ["kubectl", "top", "pods", "-n", namespace, "--no-headers"],
                capture_output=True, text=True, env=env, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        # 无表头格式: NAME CPU MEMORY
                        # 有表头格式: NAMESPACE NAME CPU MEMORY
                        if len(parts) >= 3:
                            if len(parts) == 3:
                                # 无表头: NAME CPU MEMORY
                                name = parts[0]
                                cpu_str = parts[1]
                                mem_str = parts[2]
                            else:
                                # 有表头: NAMESPACE NAME CPU MEMORY
                                name = parts[1]
                                cpu_str = parts[2]
                                mem_str = parts[3]
                            pod_metrics_map[name] = {
                                "cpu_usage": round(_parse_cpu_value(cpu_str), 4),
                                "memory_usage": _parse_resource_value(mem_str),
                            }
        except Exception as e:
            logger.warning(f"无法获取 Pod metrics: {e}")
        finally:
            if kubeconfig_path:
                os.unlink(kubeconfig_path)

    for pod in filtered_pods:
        cpu_request, cpu_limit, memory_request, memory_limit = 0.0, 0.0, 0, 0
        if pod.spec.containers:
            for container in pod.spec.containers:
                if container.resources and container.resources.requests:
                    cpu_req = container.resources.requests.get('cpu')
                    mem_req = container.resources.requests.get('memory')
                    if cpu_req:
                        cpu_request += _parse_cpu_value(str(cpu_req))
                    if mem_req:
                        memory_request += _parse_resource_value(str(mem_req))
                if container.resources and container.resources.limits:
                    cpu_lim = container.resources.limits.get('cpu')
                    mem_lim = container.resources.limits.get('memory')
                    if cpu_lim:
                        cpu_limit += _parse_cpu_value(str(cpu_lim))
                    if mem_lim:
                        memory_limit += _parse_resource_value(str(mem_lim))

        pod_name = pod.metadata.name
        metrics = pod_metrics_map.get(pod_name, {})

        # 获取 Pod 状态
        status = "Unknown"
        if pod.status:
            if pod.status.phase:
                status = pod.status.phase

        # 获取 Ready 信息
        ready = "0/0"
        restarts = 0
        if pod.status and pod.status.container_statuses:
            total = len(pod.status.container_statuses)
            r = sum(1 for c in pod.status.container_statuses if c.ready)
            ready = f"{r}/{total}"
            restarts = sum(c.restart_count for c in pod.status.container_statuses)

        items.append({
            "name": pod_name,
            "namespace": pod.metadata.namespace,
            "phase": status,
            "ready": ready,
            "restarts": restarts,
            "age": _get_age(pod.metadata.creation_timestamp),
            "node": pod.spec.node_name if pod.spec else None,
            "ip": pod.status.pod_ip if pod.status else None,
            "cpu_request": round(cpu_request, 4),
            "cpu_limit": round(cpu_limit, 4),
            "memory_request": memory_request,
            "memory_limit": memory_limit,
            "cpu_usage": metrics.get("cpu_usage"),
            "memory_usage": metrics.get("memory_usage"),
        })

    return {"workload": workload_info, "items": items, "total": len(items)}


def list_events(api_client, namespace: str | None = None, limit: int = 100) -> list[dict]:
    """列出 Events"""
    v1 = client.CoreV1Api(api_client)
    if namespace:
        events = v1.list_namespaced_event(namespace=namespace, limit=limit)
    else:
        events = v1.list_event_for_all_namespaces(limit=limit)

    result = []
    for e in events.items:
        result.append({
            "name": e.metadata.name,
            "namespace": e.metadata.namespace,
            "type": e.type or 'Normal',
            "reason": e.reason or '',
            "message": e.message or '',
            "source": e.source.component if e.source else '',
            "age": _get_age(e.metadata.creation_timestamp),
            "count": e.count or 1,
            "last_timestamp": e.last_timestamp.isoformat() if e.last_timestamp else '',
            "involved_object": f"{e.involved_object.kind}/{e.involved_object.name}" if e.involved_object else '',
        })
    # 按时间倒序
    result.sort(key=lambda x: x['last_timestamp'] or '', reverse=True)
    return result


def list_pod_events(api_client, namespace: str, pod_name: str, limit: int = 100) -> list[dict]:
    """列出与特定 Pod 相关的事件（通过 fieldSelector 筛选）

    Args:
        api_client: K8s API client
        namespace: 命名空间
        pod_name: Pod 名称
        limit: 返回事件数量上限

    Returns:
        事件列表，按时间倒序
    """
    v1 = client.CoreV1Api(api_client)

    # 使用 fieldSelector 筛选与该 Pod 相关的事件
    # fieldSelector 格式: involvedObject.name=<pod_name>,involvedObject.kind=Pod
    field_selector = f"involvedObject.name={pod_name},involvedObject.kind=Pod"

    try:
        events = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
            limit=limit
        )
    except Exception as e:
        logger.warning(f"获取 Pod 事件失败: {namespace}/{pod_name}, 原因: {e}")
        return []

    result = []
    for e in events.items:
        result.append({
            "name": e.metadata.name,
            "namespace": e.metadata.namespace,
            "type": e.type or 'Normal',
            "reason": e.reason or '',
            "message": e.message or '',
            "source": e.source.component if e.source else '',
            "age": _get_age(e.metadata.creation_timestamp),
            "count": e.count or 1,
            "last_timestamp": e.last_timestamp.isoformat() if e.last_timestamp else '',
            "first_timestamp": e.first_timestamp.isoformat() if e.first_timestamp else '',
            "involved_object": f"{e.involved_object.kind}/{e.involved_object.name}" if e.involved_object else '',
        })

    # 按时间倒序
    result.sort(key=lambda x: x['last_timestamp'] or '', reverse=True)
    return result


def get_cluster_overview(api_client) -> dict:
    """获取集群基础统计信息

    返回:
    - node_count: 节点数量
    - namespace_count: 命名空间数量
    - pod_stats: Pod 统计（总数、running、pending、failed、succeeded）
    - deployment_count: Deployment 数量
    - statefulset_count: StatefulSet 数量
    - ingress_count: Ingress 数量
    - apisixroute_count: ApisixRoute 数量
    - apisixtls_count: ApisixTls 数量
    - ingressroute_count: Traefik IngressRoute 数量
    - ingressroutetcp_count: Traefik IngressRouteTCP 数量
    - ingressrouteudp_count: Traefik IngressRouteUDP 数量
    """
    v1 = client.CoreV1Api(api_client)
    apps_v1 = client.AppsV1Api(api_client)
    net_v1 = client.NetworkingV1Api(api_client)
    custom_api = client.CustomObjectsApi(api_client)

    # Pod 统计
    all_pods = v1.list_pod_for_all_namespaces()
    pod_stats = {"total": 0, "running": 0, "pending": 0, "failed": 0, "succeeded": 0}
    for pod in all_pods.items:
        pod_stats["total"] += 1
        phase = pod.status.phase if pod.status else "Unknown"
        if phase == "Running":
            pod_stats["running"] += 1
        elif phase == "Pending":
            pod_stats["pending"] += 1
        elif phase == "Failed":
            pod_stats["failed"] += 1
        elif phase == "Succeeded":
            pod_stats["succeeded"] += 1

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

    # Ingress 统计
    try:
        ingresses = net_v1.list_ingress_for_all_namespaces()
        ingress_count = len(ingresses.items)
    except Exception:
        ingress_count = 0

    # ApisixRoute 统计
    apisixroute_count = 0
    try:
        result = custom_api.list_cluster_custom_object(
            group="apisix.apache.org",
            version="v2",
            plural="apisixroutes",
        )
        apisixroute_count = len(result.get("items", []))
    except Exception:
        try:
            result = custom_api.list_cluster_custom_object(
                group="apisix.apache.org",
                version="v2beta3",
                plural="apisixroutes",
            )
            apisixroute_count = len(result.get("items", []))
        except Exception:
            pass

    # ApisixTls 统计
    apisixtls_count = 0
    try:
        result = custom_api.list_cluster_custom_object(
            group="apisix.apache.org",
            version="v2",
            plural="apisixtls",
        )
        apisixtls_count = len(result.get("items", []))
    except Exception:
        try:
            result = custom_api.list_cluster_custom_object(
                group="apisix.apache.org",
                version="v2beta3",
                plural="apisixtls",
            )
            apisixtls_count = len(result.get("items", []))
        except Exception:
            pass

    # Traefik IngressRoute 统计
    ingressroute_count = 0
    try:
        result = custom_api.list_cluster_custom_object(
            group="traefik.io",
            version="v1alpha1",
            plural="ingressroutes",
        )
        ingressroute_count = len(result.get("items", []))
    except Exception:
        pass

    # Traefik IngressRouteTCP 统计
    ingressroutetcp_count = 0
    try:
        result = custom_api.list_cluster_custom_object(
            group="traefik.io",
            version="v1alpha1",
            plural="ingressroutetcps",
        )
        ingressroutetcp_count = len(result.get("items", []))
    except Exception:
        pass

    # Traefik IngressRouteUDP 统计
    ingressrouteudp_count = 0
    try:
        result = custom_api.list_cluster_custom_object(
            group="traefik.io",
            version="v1alpha1",
            plural="ingressrouteudps",
        )
        ingressrouteudp_count = len(result.get("items", []))
    except Exception:
        pass

    return {
        "node_count": node_count,
        "namespace_count": namespace_count,
        "pod_stats": pod_stats,
        "deployment_count": deployment_count,
        "statefulset_count": statefulset_count,
        "ingress_count": ingress_count,
        "apisixroute_count": apisixroute_count,
        "apisixtls_count": apisixtls_count,
        "ingressroute_count": ingressroute_count,
        "ingressroutetcp_count": ingressroutetcp_count,
        "ingressrouteudp_count": ingressrouteudp_count,
    }


def get_node_metrics(api_client, kubeconfig_content: str = None) -> dict:
    """获取节点资源使用量

    返回:
    - items: 节点列表，每项包含 name、ip、cpu_request、cpu_limit、cpu_usage、memory_request、memory_limit、memory_usage
    - metrics_available: 是否可用 metrics-server
    """
    v1 = client.CoreV1Api(api_client)
    items = []
    metrics_available = False
    kubeconfig_path = None

    try:
        nodes = v1.list_node()
        for node in nodes.items:
            # 获取节点 IP
            node_ip = None
            if node.status.addresses:
                for addr in node.status.addresses:
                    if addr.type == "InternalIP":
                        node_ip = addr.address
                        break

            item = {
                "name": node.metadata.name,
                "ip": node_ip,
                "cpu_request": 0,
                "cpu_limit": 0,
                "cpu_usage": 0,
                "memory_request": 0,
                "memory_limit": 0,
                "memory_usage": 0,
            }
            # 获取节点 allocatable 资源
            if node.status.allocatable:
                cpu_alloc = node.status.allocatable.get('cpu')
                mem_alloc = node.status.allocatable.get('memory')
                if cpu_alloc:
                    val = _parse_cpu_value(cpu_alloc)
                    item["cpu_request"] = val
                    item["cpu_limit"] = val  # allocatable 作为节点容量
                if mem_alloc:
                    val = _parse_resource_value(mem_alloc)
                    item["memory_request"] = val
                    item["memory_limit"] = val  # allocatable 作为节点容量
            items.append(item)
    except Exception as e:
        logger.warning(f"获取节点列表失败: {e}")

    if kubeconfig_content:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name

            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            result = subprocess.run(
                ["kubectl", "top", "nodes", "--no-headers"],
                capture_output=True, text=True, env=env, timeout=30
            )
            if result.returncode == 0:
                metrics_available = True
                node_metrics = {}
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        # 输出格式: NAME   CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
                        if len(parts) >= 5:
                            name = parts[0]
                            cpu_str = parts[1]
                            cpu_percent_str = parts[2]
                            mem_str = parts[3]
                            mem_percent_str = parts[4]
                            node_metrics[name] = {
                                "cpu": _parse_cpu_value(cpu_str),
                                "cpu_percent": float(cpu_percent_str.rstrip('%')),
                                "memory": _parse_resource_value(mem_str),
                                "memory_percent": float(mem_percent_str.rstrip('%')),
                            }

                # 合并节点信息和 metrics
                for item in items:
                    name = item["name"]
                    if name in node_metrics:
                        item["cpu_usage"] = node_metrics[name].get("cpu", 0)
                        item["cpu_percent"] = node_metrics[name].get("cpu_percent", 0)
                        item["memory_usage"] = node_metrics[name].get("memory", 0)
                        item["memory_percent"] = node_metrics[name].get("memory_percent", 0)
        except Exception as e:
            logger.warning(f"无法获取节点 metrics: {e}")
        finally:
            if kubeconfig_path:
                os.unlink(kubeconfig_path)

    return {
        "items": items,
        "metrics_available": metrics_available,
    }


def get_pod_metrics(api_client, kubeconfig_content: str = None) -> dict:
    """获取 Pod 资源请求量和使用量汇总

    返回:
    - total_request: CPU/内存请求量汇总
    - total_limit: CPU/内存 limit 量汇总
    - total_usage: CPU/内存实际使用量汇总
    - items: 每 Pod 明细列表
    """
    v1 = client.CoreV1Api(api_client)

    total_cpu_request = 0.0
    total_cpu_limit = 0.0
    total_memory_request = 0
    total_memory_limit = 0
    total_cpu_usage = 0.0
    total_memory_usage = 0
    items = []

    all_pods = v1.list_pod_for_all_namespaces()
    for pod in all_pods.items:
        pod_cpu_request = 0.0
        pod_cpu_limit = 0.0
        pod_memory_request = 0
        pod_memory_limit = 0

        containers = pod.spec.containers
        for container in containers:
            if container.resources.requests:
                cpu_req = container.resources.requests.get('cpu')
                mem_req = container.resources.requests.get('memory')
                if cpu_req:
                    val = _parse_cpu_value(cpu_req)
                    pod_cpu_request += val
                    total_cpu_request += val
                if mem_req:
                    val = _parse_resource_value(mem_req)
                    pod_memory_request += val
                    total_memory_request += val
            if container.resources.limits:
                cpu_lim = container.resources.limits.get('cpu')
                mem_lim = container.resources.limits.get('memory')
                if cpu_lim:
                    val = _parse_cpu_value(cpu_lim)
                    pod_cpu_limit += val
                    total_cpu_limit += val
                if mem_lim:
                    val = _parse_resource_value(mem_lim)
                    pod_memory_limit += val
                    total_memory_limit += val

        items.append({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "cpu_request": round(pod_cpu_request, 4),
            "cpu_limit": round(pod_cpu_limit, 4),
            "memory_request": pod_memory_request,
            "memory_limit": pod_memory_limit,
            "cpu_usage": None,
            "memory_usage": None,
            "phase": pod.status.phase if pod.status else "Unknown",
        })

    # 通过 kubectl top pods 获取实际使用量
    if kubeconfig_content:
        kubeconfig_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.kubeconfig', delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name

            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            result = subprocess.run(
                ["kubectl", "top", "pods", "--all-namespaces", "--no-headers"],
                capture_output=True, text=True, env=env, timeout=60
            )
            if result.returncode == 0:
                pod_usage_map = {}
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        # 输出格式: NAMESPACE   NAME   CPU(cores)   MEMORY(bytes)
                        if len(parts) >= 4:
                            ns = parts[0]
                            name = parts[1]
                            cpu_str = parts[2]
                            mem_str = parts[3]
                            key = (ns, name)
                            pod_usage_map[key] = {
                                "cpu": _parse_cpu_value(cpu_str),
                                "memory": _parse_resource_value(mem_str),
                            }

                # 合并使用量到 items，并汇总
                for item in items:
                    key = (item["namespace"], item["name"])
                    if key in pod_usage_map:
                        usage = pod_usage_map[key]
                        item["cpu_usage"] = round(usage["cpu"], 4)
                        item["memory_usage"] = usage["memory"]
                        total_cpu_usage += usage["cpu"]
                        total_memory_usage += usage["memory"]
        except Exception as e:
            logger.warning(f"无法获取 Pod metrics: {e}")
        finally:
            if kubeconfig_path:
                os.unlink(kubeconfig_path)

    return {
        "total_request": {
            "cpu": round(total_cpu_request, 2),
            "memory": total_memory_request,
        },
        "total_limit": {
            "cpu": round(total_cpu_limit, 2),
            "memory": total_memory_limit,
        },
        "total_usage": {
            "cpu": round(total_cpu_usage, 2),
            "memory": total_memory_usage,
        },
        "items": items,
    }


def get_top_pods(
    api_client,
    kubeconfig_content: str = None,
    limit: int = 5,
    sort_by: str = "cpu",
    namespace: str = None,
    node: str = None,
) -> dict:
    """获取资源消耗最高的 Pod 列表

    Args:
        api_client: K8s API client
        kubeconfig_content: kubeconfig 内容（用于获取 metrics）
        limit: 返回数量，默认 5
        sort_by: 排序字段，cpu 或 memory
        namespace: 命名空间过滤（可选）
        node: 节点名称过滤（可选）

    Returns:
        {"cpu_top": [...], "memory_top": [...]}
    """
    v1 = client.CoreV1Api(api_client)

    # 获取 Pod 列表
    if namespace:
        all_pods = v1.list_namespaced_pod(namespace=namespace)
    elif node:
        # 使用 field_selector 按节点过滤
        all_pods = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node}")
    else:
        all_pods = v1.list_pod_for_all_namespaces()

    # 构建 Pod 基础信息和资源请求
    pod_data = []
    for pod in all_pods.items:
        cpu_request = 0.0
        memory_request = 0
        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                cpu_req = container.resources.requests.get("cpu")
                mem_req = container.resources.requests.get("memory")
                if cpu_req:
                    cpu_request += _parse_cpu_value(str(cpu_req))
                if mem_req:
                    memory_request += _parse_resource_value(str(mem_req))

        cpu_limit = 0.0
        memory_limit = 0
        for container in pod.spec.containers:
            if container.resources and container.resources.limits:
                cpu_lim = container.resources.limits.get("cpu")
                mem_lim = container.resources.limits.get("memory")
                if cpu_lim:
                    cpu_limit += _parse_cpu_value(str(cpu_lim))
                if mem_lim:
                    memory_limit += _parse_resource_value(str(mem_lim))

        pod_data.append({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "node": pod.spec.node_name or "-",
            "cpu_request": round(cpu_request, 4),
            "memory_request": memory_request,
            "cpu_limit": round(cpu_limit, 4) if cpu_limit > 0 else None,
            "memory_limit": memory_limit if memory_limit > 0 else None,
            "cpu_usage": None,
            "memory_usage": None,
            "phase": pod.status.phase if pod.status else "Unknown",
        })

    # 获取实际使用量
    if kubeconfig_content:
        kubeconfig_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".kubeconfig", delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name

            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            cmd = ["kubectl", "top", "pods"]
            if namespace:
                cmd.extend(["-n", namespace])
            else:
                cmd.append("--all-namespaces")
            cmd.append("--no-headers")

            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
            if result.returncode == 0:
                pod_usage_map = {}
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 4:
                            # 无表头格式: NAMESPACE NAME CPU MEMORY
                            # 有表头格式: NAMESPACE NAME CPU% MEMORY%
                            ns = parts[0]
                            name = parts[1]
                            cpu_str = parts[2]
                            mem_str = parts[3]
                            pod_usage_map[(ns, name)] = {
                                "cpu": _parse_cpu_value(cpu_str),
                                "memory": _parse_resource_value(mem_str),
                            }

                # 合并使用量
                for pod in pod_data:
                    key = (pod["namespace"], pod["name"])
                    if key in pod_usage_map:
                        usage = pod_usage_map[key]
                        pod["cpu_usage"] = round(usage["cpu"], 4)
                        pod["memory_usage"] = usage["memory"]
        except Exception as e:
            logger.warning(f"无法获取 Pod metrics: {e}")
        finally:
            if kubeconfig_path:
                os.unlink(kubeconfig_path)

    # 过滤出有实际使用量的 Pod
    pods_with_usage = [p for p in pod_data if p.get("cpu_usage") is not None or p.get("memory_usage") is not None]

    # 按 CPU 排序
    cpu_sorted = sorted(pods_with_usage, key=lambda x: x.get("cpu_usage") or 0, reverse=True)
    cpu_top = cpu_sorted[:limit]

    # 按内存排序
    memory_sorted = sorted(pods_with_usage, key=lambda x: x.get("memory_usage") or 0, reverse=True)
    memory_top = memory_sorted[:limit]

    return {
        "cpu_top": cpu_top,
        "memory_top": memory_top,
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
