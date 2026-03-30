/**
 * API 封装
 *
 * 通过 Vite 代理将 /api 转发至后端，接口与后端 routers 对应。
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export interface Cluster {
  id: number
  name: string
  display_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ScalingSchedule {
  id: number
  cluster_id: number
  namespace: string
  resource_type: string
  resource_name: string
  target_replicas: number
  cron_expression: string
  timezone: string
  description: string | null
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export const clusterApi = {
  list: () => api.get<Cluster[]>('/clusters'),
  create: (data: { name: string; display_name?: string; kubeconfig_content: string }) =>
    api.post<Cluster>('/clusters', data),
  get: (id: number) => api.get<Cluster>(`/clusters/${id}`),
  update: (id: number, data: { display_name?: string; is_active?: boolean }) =>
    api.put<Cluster>(`/clusters/${id}`, data),
  updateKubeconfig: (id: number, kubeconfig_content: string) =>
    api.put<Cluster>(`/clusters/${id}/kubeconfig`, { kubeconfig_content }),
  delete: (id: number) => api.delete(`/clusters/${id}`),
  test: (id: number) => api.get(`/clusters/${id}/test`),
}

export const resourceApi = {
  metricsOverview: (clusterId: number) => api.get(`/resources/${clusterId}/metrics/overview`),
  metricsNodes: (clusterId: number) => api.get(`/resources/${clusterId}/metrics/nodes`),
  metricsPods: (clusterId: number) => api.get(`/resources/${clusterId}/metrics/pods`),
  namespaces: (clusterId: number) => api.get(`/resources/${clusterId}/namespaces`),
  deployments: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/deployments`, { params: { namespace } }),
  statefulsets: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/statefulsets`, { params: { namespace } }),
  hpas: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/hpas`, { params: { namespace } }),
  rollouts: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/rollouts`, { params: { namespace } }),
  ingressroutes: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/ingressroutes`, { params: { namespace } }),
  ingressroutetcps: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/ingressroutetcps`, { params: { namespace } }),
  ingressrouteudps: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/ingressrouteudps`, { params: { namespace } }),
  pods: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/pods`, { params: { namespace } }),
  events: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/events`, { params: { namespace } }),
  services: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/services`, { params: { namespace } }),
  ingresses: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/ingresses`, { params: { namespace } }),
  apisixroutes: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/apisixroutes`, { params: { namespace } }),
  apisixtlses: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/apisixtlses`, { params: { namespace } }),
  helm: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/helm`, { params: { namespace } }),
  configmaps: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/configmaps`, { params: { namespace } }),
  secrets: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/secrets`, { params: { namespace } }),
  getYaml: (clusterId: number, resourceType: string, namespace: string, name: string) => {
      const typeMap: Record<string, string> = {
        deployments: 'deployment',
        statefulsets: 'statefulset',
        rollouts: 'rollout',
        pods: 'pod',
        services: 'service',
        ingresses: 'ingress',
        apisixroutes: 'apisixroute',
        apisixtlses: 'apisixtls',
        ingressroutes: 'ingressroute',
        ingressroutetcps: 'ingressroutetcp',
        ingressrouteudps: 'ingressrouteudp',
        configmaps: 'configmap',
        secrets: 'secret',
      }
      return api.get<{ yaml: string }>(`/resources/${clusterId}/yaml`, {
        params: {
          resource_type: typeMap[resourceType] || resourceType,
          namespace,
          name,
        },
      })
    },
  workloadPods: (clusterId: number, namespace: string, workloadKind: string, workloadName: string) =>
    api.get(`/resources/${clusterId}/workload-pods`, {
      params: { namespace, workload_kind: workloadKind, workload_name: workloadName },
    }),
  helmGetValues: (clusterId: number, namespace: string, name: string) =>
    api.get(`/resources/${clusterId}/helm-values`, { params: { namespace, name } }),
}

export const scalingApi = {
  listSchedules: (clusterId?: number) =>
    api.get<ScalingSchedule[]>('/scaling/schedules', { params: clusterId ? { cluster_id: clusterId } : {} }),
  createSchedule: (data: Partial<ScalingSchedule>) => api.post<ScalingSchedule>('/scaling/schedules', data),
  updateSchedule: (id: number, data: Partial<ScalingSchedule>) =>
    api.put<ScalingSchedule>(`/scaling/schedules/${id}`, data),
  deleteSchedule: (id: number) => api.delete(`/scaling/schedules/${id}`),
  scale: (clusterId: number, data: {
    namespace: string
    resource_type: string
    resource_name: string
    replicas: number
  }) => api.post(`/scaling/scale/${clusterId}`, data),
}

export const logsApi = {
  getPodLogs: (clusterId: number, namespace: string, podName: string, container?: string, tailLines: number = 500) => {
    const params: Record<string, any> = { namespace, pod_name: podName, tail_lines: tailLines }
    if (container) params.container = container
    return api.get<{ logs: string }>(`/logs/${clusterId}/pod`, { params })
  },
  getPodContainers: (clusterId: number, namespace: string, podName: string) =>
    api.get<{ containers: { name: string; image: string }[] }>(`/logs/${clusterId}/pod/containers`, {
      params: { namespace, pod_name: podName },
    }),
}

export const eventsApi = {
  getPodEvents: (clusterId: number, namespace: string, podName: string) =>
    api.get(`/resources/${clusterId}/pods/${namespace}/${podName}/events`),
}

export const analysisApi = {
  getWorkloadHealth: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/analysis/workload-health`, { params: namespace ? { namespace } : {} }),
  getTopPods: (clusterId: number, limit: number = 5, sortBy: 'cpu' | 'memory' = 'cpu', node?: string) =>
    api.get(`/resources/${clusterId}/metrics/top-pods`, { params: { limit, sort_by: sortBy, node: node || undefined } }),
}

export const batchApi = {
  restartPods: (clusterId: number, items: { namespace: string; name: string }[]) =>
    api.post('/batch/restart-pods', { cluster_id: clusterId, items }),
  deletePods: (clusterId: number, items: { namespace: string; name: string }[]) =>
    api.post('/batch/delete-pods', { cluster_id: clusterId, items }),
  updateLabels: (clusterId: number, items: { namespace: string; name: string }[], labels: Record<string, string>) =>
    api.post('/batch/update-labels', { cluster_id: clusterId, items, labels }),
}

export const searchApi = {
  globalSearch: (clusterId: number, keyword: string, resourceType?: string) => {
    const params: Record<string, any> = { keyword }
    if (resourceType) params.type = resourceType
    return api.get(`/search`, { params: { cluster_id: clusterId, ...params } })
  },
}

export const auditApi = {
  getAuditLogs: (clusterId?: number, limit: number = 100) =>
    api.get('/audit/logs', { params: clusterId ? { cluster_id: clusterId, limit } : { limit } }),
}
