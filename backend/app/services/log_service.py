"""
Kubernetes Pod 日志服务

提供 Pod 日志的获取和流式传输功能，支持：
- 获取历史日志（最近 N 行）
- WebSocket 流式实时日志
"""
import asyncio
import logging
import queue
import threading
from typing import AsyncGenerator, Optional

from kubernetes import client, watch
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


async def get_pod_logs(
    api_client: client.ApiClient,
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: int = 100,
    follow: bool = False,
) -> str:
    v1 = client.CoreV1Api(api_client)

    if not container_name:
        try:
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            if pod.spec and pod.spec.containers:
                container_name = pod.spec.containers[0].name
            else:
                return f"Pod {namespace}/{pod_name} 没有容器"
        except ApiException as e:
            return f"获取 Pod 信息失败: {e.reason}"

    if not container_name:
        return "未找到容器名称"

    try:
        result = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            tail_lines=tail_lines,
            timestamps=True,
        )
        return result if result else "(无日志)"
    except ApiException as e:
        logger.warning(
            "获取 Pod 日志失败: %s/%s/%s, 原因: %s",
            namespace,
            pod_name,
            container_name,
            e.reason,
        )
        return f"获取日志失败: {e.reason}"


async def stream_pod_logs(
    api_client: client.ApiClient,
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: int = 100,
) -> AsyncGenerator[str, None]:
    v1 = client.CoreV1Api(api_client)

    if not container_name:
        try:
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            if pod.spec and pod.spec.containers:
                container_name = pod.spec.containers[0].name
        except ApiException as e:
            yield f"error:获取 Pod 信息失败: {e.reason}"
            return

    if not container_name:
        yield "error:未找到容器名称"
        return

    try:
        try:
            initial_logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
                timestamps=True,
            )
            if initial_logs:
                for line in initial_logs.split("\n"):
                    if line:
                        yield f"log:{line}"
        except ApiException as e:
            if e.status != 304:
                yield f"error:获取初始日志失败: {e.reason}"
                return

        log_queue: queue.Queue = queue.Queue()
        stop_event = threading.Event()

        def watch_logs():
            try:
                w = watch.Watch()
                stream = w.stream(
                    v1.read_namespaced_pod_log,
                    name=pod_name,
                    namespace=namespace,
                    container=container_name,
                    follow=True,
                    timestamps=True,
                    pretty=True,
                )
                for line in stream:
                    if stop_event.is_set():
                        break
                    log_queue.put(f"log:{line}")
            except ApiException as e:
                if e.status != 304:
                    log_queue.put(f"error:日志流中断: {e.reason}")
            except Exception as e:
                log_queue.put(f"error:日志流异常: {str(e)}")
            finally:
                log_queue.put(None)

        thread = threading.Thread(target=watch_logs, daemon=True)
        thread.start()

        while True:
            try:
                item = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: log_queue.get(timeout=1.0)
                )
            except queue.Empty:
                if not thread.is_alive():
                    break
                continue
            if item is None:
                break
            yield item

    except Exception as e:
        logger.error("流式日志获取异常: %s/%s, 原因: %s", namespace, pod_name, e)
        yield f"error:日志流异常: {str(e)}"


def get_pod_containers(api_client: client.ApiClient, namespace: str, pod_name: str) -> list[dict]:
    v1 = client.CoreV1Api(api_client)
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        containers = []
        if pod.spec:
            for c in pod.spec.containers:
                containers.append({"name": c.name, "image": c.image})
        return containers
    except ApiException as e:
        logger.warning("获取 Pod 容器信息失败: %s/%s, 原因: %s", namespace, pod_name, e.reason)
        return []
