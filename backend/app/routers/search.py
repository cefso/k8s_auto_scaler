"""
Kubernetes 全局搜索 API

提供跨所有命名空间的资源搜索功能。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Cluster
from app.services.k8s_service import get_api_client_for_cluster

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


async def _get_cluster(db: AsyncSession, cluster_id: int) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="集群已禁用")
    return cluster


def search_crd_resources(
    api_client,
    keyword: str,
    resource_type: str | None = None,
) -> list[dict]:
    """搜索 CRD 资源（ApisixRoute, ApisixTls, IngressRoute 等）

    Args:
        api_client: K8s API client
        keyword: 搜索关键词
        resource_type: 资源类型过滤（可选）

    Returns:
        匹配的资源列表
    """
    from kubernetes import client

    custom_api = client.CustomObjectsApi(api_client)
    results = []
    keyword_lower = keyword.lower()

    # CRD 资源配置
    crds = [
        # Apisix CRDs
        {"group": "apisix.apache.org", "version": "v2", "plural": "apisixroutes", "type": "ApisixRoute"},
        {"group": "apisix.apache.org", "version": "v2", "plural": "apisixtlses", "type": "ApisixTls"},
        # Traefik CRDs
        {"group": "traefik.containo.us", "version": "v1", "plural": "ingressroutes", "type": "IngressRoute"},
        {"group": "traefik.containo.us", "version": "v1", "plural": "ingressroutetcps", "type": "IngressRouteTCP"},
        {"group": "traefik.containo.us", "version": "v1", "plural": "ingressrouteudps", "type": "IngressRouteUDP"},
    ]

    for crd in crds:
        if resource_type is None or resource_type == crd["plural"]:
            try:
                items = custom_api.list_cluster_custom_object(
                    group=crd["group"],
                    version=crd["version"],
                    plural=crd["plural"],
                )
                for item in items.get("items", []):
                    name = item.get("metadata", {}).get("name", "")
                    if keyword_lower in name.lower():
                        namespace = item.get("metadata", {}).get("namespace", "default")
                        results.append({
                            "type": crd["type"],
                            "name": name,
                            "namespace": namespace,
                        })
            except Exception as e:
                logger.warning(f"搜索 {crd['type']} 失败: {e}")

    return results


def search_resources(
    api_client,
    keyword: str,
    resource_type: str | None = None,
) -> dict:
    """全局搜索资源

    Args:
        api_client: K8s API client
        keyword: 搜索关键词
        resource_type: 资源类型过滤（可选），支持: pod, deployment, statefulset, service, ingress, configmap, secret, apisixroute, apisixtls, ingressroute, ingressroutetcp, ingressrouteudp

    Returns:
        {"items": [...], "total": int}
    """
    from kubernetes import client

    v1 = client.CoreV1Api(api_client)
    apps_v1 = client.AppsV1Api(api_client)
    net_v1 = client.NetworkingV1Api(api_client)

    results = []
    keyword_lower = keyword.lower()

    # Pod 搜索
    if resource_type is None or resource_type == "pod":
        try:
            pods = v1.list_pod_for_all_namespaces()
            for pod in pods.items:
                if keyword_lower in pod.metadata.name.lower():
                    results.append({
                        "type": "Pod",
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "status": pod.status.phase if pod.status else "Unknown",
                    })
        except Exception as e:
            logger.warning(f"搜索 Pod 失败: {e}")

    # Deployment 搜索
    if resource_type is None or resource_type == "deployment":
        try:
            deploys = apps_v1.list_deployment_for_all_namespaces()
            for d in deploys.items:
                if keyword_lower in d.metadata.name.lower():
                    results.append({
                        "type": "Deployment",
                        "name": d.metadata.name,
                        "namespace": d.metadata.namespace,
                        "replicas": d.spec.replicas or 0,
                        "ready_replicas": d.status.ready_replicas or 0,
                    })
        except Exception as e:
            logger.warning(f"搜索 Deployment 失败: {e}")

    # StatefulSet 搜索
    if resource_type is None or resource_type == "statefulset":
        try:
            sts_list = apps_v1.list_stateful_set_for_all_namespaces()
            for s in sts_list.items:
                if keyword_lower in s.metadata.name.lower():
                    results.append({
                        "type": "StatefulSet",
                        "name": s.metadata.name,
                        "namespace": s.metadata.namespace,
                        "replicas": s.spec.replicas or 0,
                        "ready_replicas": s.status.ready_replicas or 0,
                    })
        except Exception as e:
            logger.warning(f"搜索 StatefulSet 失败: {e}")

    # Service 搜索
    if resource_type is None or resource_type == "service":
        try:
            svcs = v1.list_service_for_all_namespaces()
            for svc in svcs.items:
                if keyword_lower in svc.metadata.name.lower():
                    results.append({
                        "type": "Service",
                        "name": svc.metadata.name,
                        "namespace": svc.metadata.namespace,
                        "cluster_ip": svc.spec.cluster_ip if svc.spec else "-",
                        " ports": [p.port for p in svc.spec.ports] if svc.spec and svc.spec.ports else [],
                    })
        except Exception as e:
            logger.warning(f"搜索 Service 失败: {e}")

    # Ingress 搜索
    if resource_type is None or resource_type == "ingress":
        try:
            ings = net_v1.list_ingress_for_all_namespaces()
            for ing in ings.items:
                if keyword_lower in ing.metadata.name.lower():
                    results.append({
                        "type": "Ingress",
                        "name": ing.metadata.name,
                        "namespace": ing.metadata.namespace,
                        "hosts": [r.host for r in ing.spec.rules] if ing.spec and ing.spec.rules else [],
                    })
        except Exception as e:
            logger.warning(f"搜索 Ingress 失败: {e}")

    # ConfigMap 搜索
    if resource_type is None or resource_type == "configmap":
        try:
            cms = v1.list_config_map_for_all_namespaces()
            for cm in cms.items:
                if keyword_lower in cm.metadata.name.lower():
                    results.append({
                        "type": "ConfigMap",
                        "name": cm.metadata.name,
                        "namespace": cm.metadata.namespace,
                        "data_keys": list(cm.data) if cm.data else [],
                    })
        except Exception as e:
            logger.warning(f"搜索 ConfigMap 失败: {e}")

    # Secret 搜索
    if resource_type is None or resource_type == "secret":
        try:
            secrets = v1.list_secret_for_all_namespaces()
            for s in secrets.items:
                if keyword_lower in s.metadata.name.lower():
                    results.append({
                        "type": "Secret",
                        "name": s.metadata.name,
                        "namespace": s.metadata.namespace,
                        "secret_type": s.type or "Opaque",
                    })
        except Exception as e:
            logger.warning(f"搜索 Secret 失败: {e}")

    # CRD 资源搜索（ApisixRoute, ApisixTls, IngressRoute 等）
    crd_results = search_crd_resources(api_client, keyword, resource_type)
    results.extend(crd_results)

    return {"items": results, "total": len(results)}


@router.get("")
async def global_search(
    cluster_id: int,
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    type: str | None = Query(None, description="资源类型过滤（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """全局搜索集群资源

    支持搜索以下资源类型：
    - pod: Pod
    - deployment: Deployment
    - statefulset: StatefulSet
    - service: Service
    - ingress: Ingress
    - configmap: ConfigMap
    - secret: Secret
    - apisixroute: ApisixRoute
    - apisixtls: ApisixTls
    - ingressroute: IngressRoute
    - ingressroutetcp: IngressRouteTCP
    - ingressrouteudp: IngressRouteUDP

    如果不指定 type，则搜索所有类型。
    """
    if not keyword or len(keyword) < 1:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)

    try:
        result = search_resources(api_client, keyword, type)
        return {
            "cluster_id": cluster_id,
            "keyword": keyword,
            "type": type,
            **result,
        }
    except Exception as e:
        logger.error(f"全局搜索失败: cluster={cluster.name}, keyword={keyword}, 原因: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
