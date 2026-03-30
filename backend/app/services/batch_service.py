"""
Kubernetes 批量操作服务

提供：
- 批量重启 Pod（通过删除 Pod 实现）
- 批量删除 Pod
- 批量更新 Label
"""
import logging

from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


def restart_pods(api_client: client.ApiClient, items: list[dict]) -> dict:
    """批量重启 Pod（通过删除 Pod 实现，Kubernetes 会自动重新创建）

    Args:
        api_client: K8s API client
        items: [{"namespace": "ns1", "name": "pod1"}, ...]

    Returns:
        {"success": [{"namespace": "ns1", "name": "pod1"}, ...], "failed": [...]}
    """
    v1 = client.CoreV1Api(api_client)
    success = []
    failed = []

    for item in items:
        namespace = item.get("namespace")
        name = item.get("name")
        if not namespace or not name:
            failed.append({"item": item, "error": "缺少 namespace 或 name"})
            continue

        try:
            # 删除 Pod（不等待终止）
            v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                body=client.V1DeleteOptions(),
                grace_period_seconds=0,  # 立即删除
            )
            logger.info(f"重启 Pod 成功: {namespace}/{name}")
            success.append({"namespace": namespace, "name": name})
        except ApiException as e:
            logger.warning(f"重启 Pod 失败: {namespace}/{name}, 原因: {e.reason}")
            failed.append({"namespace": namespace, "name": name, "error": e.reason})
        except Exception as e:
            logger.error(f"重启 Pod 异常: {namespace}/{name}, 原因: {str(e)}")
            failed.append({"namespace": namespace, "name": name, "error": str(e)})

    return {"success": success, "failed": failed, "total": len(items)}


def delete_pods(api_client: client.ApiClient, items: list[dict]) -> dict:
    """批量删除 Pod

    Args:
        api_client: K8s API client
        items: [{"namespace": "ns1", "name": "pod1"}, ...]

    Returns:
        {"success": [...], "failed": [...]}
    """
    v1 = client.CoreV1Api(api_client)
    success = []
    failed = []

    for item in items:
        namespace = item.get("namespace")
        name = item.get("name")
        if not namespace or not name:
            failed.append({"item": item, "error": "缺少 namespace 或 name"})
            continue

        try:
            v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                body=client.V1DeleteOptions(),
                grace_period_seconds=30,
            )
            logger.info(f"删除 Pod 成功: {namespace}/{name}")
            success.append({"namespace": namespace, "name": name})
        except ApiException as e:
            logger.warning(f"删除 Pod 失败: {namespace}/{name}, 原因: {e.reason}")
            failed.append({"namespace": namespace, "name": name, "error": e.reason})
        except Exception as e:
            logger.error(f"删除 Pod 异常: {namespace}/{name}, 原因: {str(e)}")
            failed.append({"namespace": namespace, "name": name, "error": str(e)})

    return {"success": success, "failed": failed, "total": len(items)}


def update_pod_labels(
    api_client: client.ApiClient,
    items: list[dict],
    labels: dict,
) -> dict:
    """批量更新 Pod 的 Labels

    Args:
        api_client: K8s API client
        items: [{"namespace": "ns1", "name": "pod1"}, ...]
        labels: 要添加/更新的 label 字典 {"key1": "value1", "key2": "value2"}

    Returns:
        {"success": [...], "failed": [...]}
    """
    v1 = client.CoreV1Api(api_client)
    success = []
    failed = []

    for item in items:
        namespace = item.get("namespace")
        name = item.get("name")
        if not namespace or not name:
            failed.append({"item": item, "error": "缺少 namespace 或 name"})
            continue

        try:
            # 获取当前 pod
            pod = v1.read_namespaced_pod(name=name, namespace=namespace)

            # 更新 labels
            if pod.metadata.labels is None:
                pod.metadata.labels = {}
            pod.metadata.labels.update(labels)

            #  patch 更新
            v1.patch_namespaced_pod(
                name=name,
                namespace=namespace,
                body=pod,
            )
            logger.info(f"更新 Pod Labels 成功: {namespace}/{name}, labels={labels}")
            success.append({"namespace": namespace, "name": name})
        except ApiException as e:
            logger.warning(f"更新 Pod Labels 失败: {namespace}/{name}, 原因: {e.reason}")
            failed.append({"namespace": namespace, "name": name, "error": e.reason})
        except Exception as e:
            logger.error(f"更新 Pod Labels 异常: {namespace}/{name}, 原因: {str(e)}")
            failed.append({"namespace": namespace, "name": name, "error": str(e)})

    return {"success": success, "failed": failed, "total": len(items)}
