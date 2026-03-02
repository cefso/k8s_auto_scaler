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
  delete: (id: number) => api.delete(`/clusters/${id}`),
  test: (id: number) => api.get(`/clusters/${id}/test`),
}

export const resourceApi = {
  namespaces: (clusterId: number) => api.get(`/resources/${clusterId}/namespaces`),
  deployments: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/deployments`, { params: { namespace } }),
  statefulsets: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/statefulsets`, { params: { namespace } }),
  rollouts: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/rollouts`, { params: { namespace } }),
  pods: (clusterId: number, namespace?: string) =>
    api.get(`/resources/${clusterId}/pods`, { params: { namespace } }),
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
