"""
Kubernetes 集群服务

- 从数据库解密 kubeconfig 并创建 K8s API 客户端
- 封装各类资源（Deployment、Pod、Service 等）的列表与扩缩容操作
- 支持 CRD：Argo Rollout、Apache APISIX Route/TLS、Helm Release
"""
import re
import yaml
from datetime import datetime, timezone
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.models import Cluster
from app.crypto_utils import decrypt_kubeconfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


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


def list_helm_releases(api_client, namespace: str | None = None) -> list[dict]:
    """列出 Helm 应用 (通过 Helm release Secrets)"""
    v1 = client.CoreV1Api(api_client)
    label_selector = "app.kubernetes.io/managed-by=Helm"
    try:
        if namespace:
            secrets = v1.list_namespaced_secret(
                namespace=namespace,
                label_selector=label_selector,
            )
        else:
            secrets = v1.list_secret_for_all_namespaces(
                label_selector=label_selector,
            )
    except ApiException:
        return []

    # 解析 release 信息，同一 release 只保留最新 revision
    releases: dict[tuple[str, str], dict] = {}
    for s in secrets.items:
        if not s.metadata or s.type != "helm.sh/release.v1":
            continue
        ann = s.metadata.annotations or {}
        release_name = ann.get("meta.helm.sh/release-name") or _parse_release_name(s.metadata.name)
        ns = s.metadata.namespace or ann.get("meta.helm.sh/release-namespace", "")
        revision = _parse_helm_revision(s.metadata.name)
        key = (ns, release_name)
        if key not in releases or revision > releases[key].get("revision", 0):
            releases[key] = {
                "name": release_name,
                "namespace": ns,
                "revision": revision,
                "status": "deployed",
                "age": _get_age(s.metadata.creation_timestamp),
            }

    return sorted(releases.values(), key=lambda x: (x["namespace"], x["name"]))


def _parse_release_name(secret_name: str) -> str:
    """从 secret 名解析 release 名: sh.helm.release.v1.<name>.v<rev>"""
    m = re.search(r"sh\.helm\.release\.v\d+\.(.+)\.v\d+$", secret_name)
    return m.group(1) if m else secret_name


def _parse_helm_revision(secret_name: str) -> int:
    """解析 revision 数字"""
    m = re.search(r"\.v(\d+)$", secret_name)
    return int(m.group(1)) if m else 0


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


def scale_deployment(
    api_client, namespace: str, name: str, replicas: int
) -> dict:
    """扩展 Deployment 副本数"""
    apps_v1 = client.AppsV1Api(api_client)
    try:
        deploy = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
        deploy.spec.replicas = replicas
        apps_v1.patch_namespaced_deployment_scale(
            name=name,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        return {"success": True, "message": f"已将 {name} 扩缩至 {replicas} 副本"}
    except ApiException as e:
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
        return {"success": True, "message": f"已将 {name} 扩缩至 {replicas} 副本"}
    except ApiException as e:
        return {"success": False, "message": str(e.reason)}


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
