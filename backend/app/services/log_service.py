"""
Kubernetes Pod 日志服务

提供 Pod 日志的获取和流式传输功能，支持：
- 获取历史日志（最近 N 行）
- WebSocket 流式实时日志
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional

from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes import watch

from app.models import Cluster
from app.crypto_utils import decrypt_kubeconfig

logger = logging.getLogger(__name__)


def get_api_client_for_cluster(cluster: Cluster):
    """根据 Cluster 模型解密 kubeconfig 并返回该集群的 K8s ApiClient。"""
    import yaml
    content = decrypt_kubeconfig(cluster.kubeconfig_encrypted)
    config_dict = yaml.safe_load(content)
    if not config_dict:
        raise ValueError("kubeconfig 内容为空")
    return client.ApiClient(client.config.new_client_from_config_dict(config_dict))


async def get_pod_logs(
    api_client: client.ApiClient,
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: int = 100,
    follow: bool = False,
) -> str:
    """获取 Pod 的历史日志（非流式）

    Args:
        api_client: K8s API client
        namespace: 命名空间
        pod_name: Pod 名称
        container_name: 容器名称（可选，默认取第一个容器）
        tail_lines: 返回最近 N 行
        follow: 是否持续跟踪（此参数在此函数中不生效，仅作标记）

    Returns:
        日志内容字符串
    """
    v1 = client.CoreV1Api(api_client)

    # 如果没有指定容器名，获取 Pod 的第一个容器
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
        return f"未找到容器名称"

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
        logger.warning(f"获取 Pod 日志失败: {namespace}/{pod_name}/{container_name}, 原因: {e.reason}")
        return f"获取日志失败: {e.reason}"


async def stream_pod_logs(
    api_client: client.ApiClient,
    namespace: str,
    pod_name: str,
    container_name: Optional[str] = None,
    tail_lines: int = 100,
) -> AsyncGenerator[str, None]:
    """流式获取 Pod 日志（用于 WebSocket）

    Args:
        api_client: K8s API client
        namespace: 命名空间
        pod_name: Pod 名称
        container_name: 容器名称（可选）
        tail_lines: 初始返回最近 N 行

    Yields:
        日志内容片段
    """
    v1 = client.CoreV1Api(api_client)

    # 如果没有指定容器名，获取 Pod 的第一个容器
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

    # 使用 watch 功能进行流式日志获取
    try:
        # 首先获取初始日志
        try:
            initial_logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
                timestamps=True,
            )
            if initial_logs:
                # 分行返回初始日志
                for line in initial_logs.split('\n'):
                    if line:
                        yield f"log:{line}"
        except ApiException as e:
            if e.status != 304:  # 304 表示没有日志
                yield f"error:获取初始日志失败: {e.reason}"
                return

        # 然后使用 watch 持续跟踪新日志
        # 注意：kubernetes.watch 的 watch 功能是同步的，需要在线程池中运行
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
                    yield f"log:{line}"
            except ApiException as e:
                if e.status != 304:
                    yield f"error:日志流中断: {e.reason}"
            except Exception as e:
                yield f"error:日志流异常: {str(e)}"

        # 在线程池中运行同步的 watch
        loop = asyncio.get_event_loop()
        async for line in _stream_in_thread(loop, watch_logs):
            yield line

    except Exception as e:
        logger.error(f"流式日志获取异常: {namespace}/{pod_name}, 原因: {str(e)}")
        yield f"error:日志流异常: {str(e)}"


async def _stream_in_thread(loop, gen_func):
    """在线程池中运行同步生成器并异步 yield 结果"""
    import concurrent.futures

    def run_gen():
        return list(gen_func())

    pool = concurrent.futures.ThreadPoolExecutor()
    future = pool.submit(run_gen)

    try:
        while not future.done():
            await asyncio.sleep(0.1)
        results = future.result()
        for item in results:
            yield item
    finally:
        pool.shutdown(wait=False)


def get_pod_containers(api_client: client.ApiClient, namespace: str, pod_name: str) -> list[dict]:
    """获取 Pod 的所有容器信息

    Returns:
        [{"name": "container1", "image": "..."}, ...]
    """
    v1 = client.CoreV1Api(api_client)
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        containers = []
        if pod.spec:
            for c in pod.spec.containers:
                containers.append({
                    "name": c.name,
                    "image": c.image,
                })
        return containers
    except ApiException as e:
        logger.warning(f"获取 Pod 容器信息失败: {namespace}/{pod_name}, 原因: {e.reason}")
        return []
