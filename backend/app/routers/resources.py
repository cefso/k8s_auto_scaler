"""
K8s 资源查询 API

按集群与资源类型查询 Deployment、Pod、Service、Ingress、ConfigMap、Secret 等，
支持命名空间筛选，部分资源支持 YAML 查看。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Cluster
from app.services.k8s_service import (
    get_api_client_for_cluster,
    get_kubeconfig_content_for_cluster,
    get_resource_yaml,
    get_cluster_overview,
    get_node_metrics,
    get_pod_metrics,
    list_namespaces,
    list_deployments,
    list_statefulsets,
    list_rollouts,
    list_pods,
    list_events,
    list_pod_events,
    list_services,
    list_ingresses,
    list_apisixroutes,
    list_apisixtlses,
    list_helm_releases,
    helm_get_values,
    list_configmaps,
    list_secrets,
    list_traefikingresses,
    list_traefikingresstcps,
    list_traefikingressudps,
    get_workload_pods,
    get_top_pods,
    list_hpas,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resources", tags=["resources"])


async def _get_cluster(db: AsyncSession, cluster_id: int) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="集群已禁用")
    return cluster


@router.get("/{cluster_id}/metrics/overview")
async def get_cluster_overview_endpoint(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """获取集群基础统计信息（节点数、命名空间数、Pod 统计、Deployment/StatefulSet 数量）"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    overview = get_cluster_overview(api_client)
    return {"cluster_id": cluster_id, **overview}


@router.get("/{cluster_id}/metrics/nodes")
async def get_node_metrics_endpoint(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """获取节点资源使用量（需集群安装 metrics-server）"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = get_node_metrics(api_client, kubeconfig_content)
    return {"cluster_id": cluster_id, **result}


@router.get("/{cluster_id}/metrics/pods")
async def get_pod_metrics_endpoint(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """获取 Pod 资源请求量/limit 量/实际使用量汇总"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = get_pod_metrics(api_client, kubeconfig_content)
    return {"cluster_id": cluster_id, **result}


@router.get("/{cluster_id}/namespaces")
async def get_namespaces(cluster_id: int, db: AsyncSession = Depends(get_db)):
    """获取命名空间列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_namespaces(api_client)
    return {"cluster_id": cluster_id, "resource_type": "Namespace", "items": items, "total": len(items)}


@router.get("/{cluster_id}/deployments")
async def get_deployments(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Deployment 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_deployments(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Deployment", "items": items, "total": len(items)}


@router.get("/{cluster_id}/statefulsets")
async def get_statefulsets(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 StatefulSet 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_statefulsets(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "StatefulSet", "items": items, "total": len(items)}


@router.get("/{cluster_id}/hpas")
async def get_hpas(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 HPA (Horizontal Pod Autoscaler) 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_hpas(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "HPA", "items": items, "total": len(items)}


@router.get("/{cluster_id}/rollouts")
async def get_rollouts(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Argo Rollout 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_rollouts(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Rollout", "items": items, "total": len(items)}


@router.get("/{cluster_id}/services")
async def get_services(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Service 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_services(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Service", "items": items, "total": len(items)}


@router.get("/{cluster_id}/ingresses")
async def get_ingresses(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Ingress 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_ingresses(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Ingress", "items": items, "total": len(items)}


@router.get("/{cluster_id}/apisixroutes")
async def get_apisixroutes(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Apache APISIX Route 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_apisixroutes(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "ApisixRoute", "items": items, "total": len(items)}


@router.get("/{cluster_id}/apisixtlses")
async def get_apisixtlses(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Apache APISIX TLS 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_apisixtlses(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "ApisixTls", "items": items, "total": len(items)}


@router.get("/{cluster_id}/ingressroutes")
async def get_traefik_ingress_routes(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Traefik IngressRoute 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_traefikingresses(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "IngressRoute", "items": items, "total": len(items)}


@router.get("/{cluster_id}/ingressroutetcps")
async def get_traefik_ingress_route_tcps(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Traefik IngressRouteTCP 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_traefikingresstcps(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "IngressRouteTCP", "items": items, "total": len(items)}


@router.get("/{cluster_id}/ingressrouteudps")
async def get_traefik_ingress_route_udps(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Traefik IngressRouteUDP 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_traefikingressudps(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "IngressRouteUDP", "items": items, "total": len(items)}


@router.get("/{cluster_id}/helm")
async def get_helm_releases(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Helm 应用列表"""
    cluster = await _get_cluster(db, cluster_id)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = list_helm_releases(kubeconfig_content, namespace)
    return {
        "cluster_id": cluster_id,
        "resource_type": "Helm",
        "items": result["items"],
        "total": len(result["items"]),
        "helm_available": result["helm_available"],
        "error": result["error"],
    }


@router.get("/{cluster_id}/helm-values")
async def get_helm_values(
    cluster_id: int,
    namespace: str = Query(...),
    name: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取 Helm release 的 values 文件"""
    cluster = await _get_cluster(db, cluster_id)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = helm_get_values(kubeconfig_content, namespace, name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"cluster_id": cluster_id, "name": name, "namespace": namespace, "values": result["values"]}


@router.get("/{cluster_id}/pods")
async def get_pods(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Pod 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_pods(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Pod", "items": items, "total": len(items)}


@router.get("/{cluster_id}/events")
async def get_events(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Event 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_events(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Event", "items": items, "total": len(items)}


@router.get("/{cluster_id}/configmaps")
async def get_configmaps(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 ConfigMap 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_configmaps(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "ConfigMap", "items": items, "total": len(items)}


@router.get("/{cluster_id}/secrets")
async def get_secrets(
    cluster_id: int,
    namespace: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取 Secret 列表"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_secrets(api_client, namespace)
    return {"cluster_id": cluster_id, "resource_type": "Secret", "items": items, "total": len(items)}


@router.get("/{cluster_id}/yaml")
async def get_resource_yaml_endpoint(
    cluster_id: int,
    resource_type: str = Query(..., description="deployment, statefulset, rollout, pod, service, ingress, apisixroute, apisixtls, configmap, secret"),
    namespace: str = Query(...),
    name: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取资源的 YAML 内容"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    try:
        yaml_content = get_resource_yaml(api_client, resource_type, namespace, name)
        logger.debug(f"获取 YAML 成功: cluster={cluster.name}, type={resource_type}, "
                     f"namespace={namespace}, name={name}")
        return {"yaml": yaml_content, "resource_type": resource_type, "namespace": namespace, "name": name}
    except Exception as e:
        logger.warning(f"获取 YAML 失败: cluster={cluster.name}, type={resource_type}, "
                       f"namespace={namespace}, name={name}, 原因: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{cluster_id}/workload-pods")
async def get_workload_pods_endpoint(
    cluster_id: int,
    namespace: str = Query(...),
    workload_kind: str = Query(...),
    workload_name: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取特定工作负载的 Pod 列表及资源使用量"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = get_workload_pods(api_client, namespace, workload_kind, workload_name, kubeconfig_content)
    return {"cluster_id": cluster_id, **result}


@router.get("/{cluster_id}/pods/{namespace}/{pod_name}/events")
async def get_pod_events_endpoint(
    cluster_id: int,
    namespace: str,
    pod_name: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取与特定 Pod 相关的事件"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    items = list_pod_events(api_client, namespace, pod_name, limit)
    return {"cluster_id": cluster_id, "namespace": namespace, "pod_name": pod_name, "items": items, "total": len(items)}


@router.get("/{cluster_id}/metrics/top-pods")
async def get_top_pods_endpoint(
    cluster_id: int,
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    sort_by: str = Query("cpu", description="排序字段: cpu 或 memory"),
    namespace: str | None = Query(None, description="命名空间过滤（可选）"),
    node: str | None = Query(None, description="节点名称过滤（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """获取资源消耗最高的 Pod 列表（Top N）"""
    cluster = await _get_cluster(db, cluster_id)
    api_client = get_api_client_for_cluster(cluster)
    kubeconfig_content = get_kubeconfig_content_for_cluster(cluster)
    result = get_top_pods(
        api_client=api_client,
        kubeconfig_content=kubeconfig_content,
        limit=limit,
        sort_by=sort_by,
        namespace=namespace,
        node=node,
    )
    return {"cluster_id": cluster_id, **result}
