<template>
  <div class="dashboard">
    <div v-if="loading" class="empty-state">Loading...</div>
    <div v-else-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>
    <template v-else>
      <!-- 统计卡片 -->
      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-label">集群节点</div>
          <div class="stat-value">{{ overview?.node_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">命名空间</div>
          <div class="stat-value">{{ overview?.namespace_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Pod 总数</div>
          <div class="stat-value">{{ overview?.pod_stats?.total ?? '-' }}</div>
        </div>
        <div class="stat-card stat-card-running">
          <div class="stat-label">Pod 运行中</div>
          <div class="stat-value">{{ overview?.pod_stats?.running ?? '-' }}</div>
        </div>
        <div class="stat-card stat-card-pending">
          <div class="stat-label">Pod 等待中</div>
          <div class="stat-value">{{ overview?.pod_stats?.pending ?? '-' }}</div>
        </div>
        <div class="stat-card stat-card-failed">
          <div class="stat-label">Pod 异常</div>
          <div class="stat-value">{{ overview?.pod_stats?.failed ?? '-' }}</div>
        </div>
        <div class="stat-card stat-card-succeeded">
          <div class="stat-label">Pod 完成</div>
          <div class="stat-value">{{ overview?.pod_stats?.succeeded ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Deployment</div>
          <div class="stat-value">{{ overview?.deployment_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">StatefulSet</div>
          <div class="stat-value">{{ overview?.statefulset_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Ingress</div>
          <div class="stat-value">{{ overview?.ingress_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ApisixRoute</div>
          <div class="stat-value">{{ overview?.apisixroute_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ApisixTls</div>
          <div class="stat-value">{{ overview?.apisixtls_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">IngressRoute</div>
          <div class="stat-value">{{ overview?.ingressroute_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">IngressRouteTCP</div>
          <div class="stat-value">{{ overview?.ingressroutetcp_count ?? '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">IngressRouteUDP</div>
          <div class="stat-value">{{ overview?.ingressrouteudp_count ?? '-' }}</div>
        </div>
      </div>

      <!-- Pod Resources -->
      <div class="card" style="margin-top: 1.5rem">
        <div class="card-header">
          <span class="card-title">Pod 资源汇总</span>
          <span v-if="!podMetrics?.total_usage" class="card-badge warning">metrics-server not available, usage data unavailable</span>
        </div>
        <div class="card-body">
          <div class="pod-resource-summary">
            <div class="resource-column">
              <div class="resource-column-header">CPU</div>
              <div class="resource-row">
                <span class="resource-label">Request</span>
                <span class="resource-value">{{ podMetrics?.total_request?.cpu ?? '-' }} Cores</span>
              </div>
              <div class="resource-row">
                <span class="resource-label">Limit</span>
                <span class="resource-value">{{ podMetrics?.total_limit?.cpu ?? '-' }} Cores</span>
              </div>
              <div class="resource-row">
                <span class="resource-label">Usage</span>
                <span class="resource-value" :class="{ 'text-muted': !podMetrics?.total_usage?.cpu }">
                  {{ podMetrics?.total_usage?.cpu ? podMetrics.total_usage.cpu + ' Cores' : '-' }}
                </span>
              </div>
            </div>
            <div class="resource-column">
              <div class="resource-column-header">Memory</div>
              <div class="resource-row">
                <span class="resource-label">Request</span>
                <span class="resource-value">{{ formatBytes(podMetrics?.total_request?.memory) }}</span>
              </div>
              <div class="resource-row">
                <span class="resource-label">Limit</span>
                <span class="resource-value">{{ formatBytes(podMetrics?.total_limit?.memory) }}</span>
              </div>
              <div class="resource-row">
                <span class="resource-label">Usage</span>
                <span class="resource-value" :class="{ 'text-muted': !podMetrics?.total_usage?.memory }">
                  {{ formatBytes(podMetrics?.total_usage?.memory) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Top N Pods -->
      <div class="top-pods-section" style="margin-top: 1.5rem">
        <div class="top-pods-grid">
          <div class="card">
            <div class="card-header">
              <span class="card-title">CPU 消耗 Top 5 Pods</span>
            </div>
            <div class="card-body">
              <div v-if="topPodsLoading" class="empty-state">加载中...</div>
              <div v-else-if="!topPods?.cpu_top?.length" class="empty-state">暂无数据</div>
              <div v-else class="top-pods-list">
                <div v-for="(pod, index) in topPods.cpu_top" :key="pod.name + pod.namespace" class="top-pod-item">
                  <span class="top-pod-rank" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
                  <div class="top-pod-info">
                    <span class="top-pod-name">{{ pod.namespace }}/{{ pod.name }}</span>
                    <span class="top-pod-usage">{{ pod.cpu_usage != null ? pod.cpu_usage + ' Cores' : '-' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="card-header">
              <span class="card-title">内存消耗 Top 5 Pods</span>
            </div>
            <div class="card-body">
              <div v-if="topPodsLoading" class="empty-state">加载中...</div>
              <div v-else-if="!topPods?.memory_top?.length" class="empty-state">暂无数据</div>
              <div v-else class="top-pods-list">
                <div v-for="(pod, index) in topPods.memory_top" :key="pod.name + pod.namespace" class="top-pod-item">
                  <span class="top-pod-rank" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
                  <div class="top-pod-info">
                    <span class="top-pod-name">{{ pod.namespace }}/{{ pod.name }}</span>
                    <span class="top-pod-usage">{{ pod.memory_usage != null ? formatBytes(pod.memory_usage) : '-' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Events -->
      <div class="card" style="margin-top: 1.5rem">
        <div class="card-header">
          <span class="card-title">集群事件</span>
        </div>
        <div class="card-body">
          <div v-if="eventsLoading" class="empty-state">Loading...</div>
          <div v-else-if="!events?.length" class="empty-state">暂无事件数据</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>类型</th>
                  <th>原因</th>
                  <th>对象</th>
                  <th>消息</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="event in events" :key="event.name + event.last_timestamp">
                  <td>
                    <span class="event-type" :class="event.type === 'Warning' ? 'event-warning' : 'event-normal'">
                      {{ event.type }}
                    </span>
                  </td>
                  <td>{{ event.reason || '-' }}</td>
                  <td class="event-object">{{ event.involved_object || '-' }}</td>
                  <td class="event-message">{{ event.message || '-' }}</td>
                  <td>{{ event.age || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  clusterId: number
}>()

const overview = ref<any>(null)
const podMetrics = ref<any>(null)
const topPods = ref<any>(null)
const events = ref<any[]>([])
const eventsLoading = ref(false)
const topPodsLoading = ref(false)
const loading = ref(true)
const error = ref('')

async function loadOverview() {
  try {
    const { resourceApi } = await import('@/api')
    const res = await resourceApi.metricsOverview(props.clusterId)
    overview.value = res.data
  } catch (e: any) {
    throw new Error(e.response?.data?.detail || e.message || 'Failed to load overview')
  }
}

async function loadPodMetrics() {
  try {
    const { resourceApi } = await import('@/api')
    const res = await resourceApi.metricsPods(props.clusterId)
    podMetrics.value = res.data
  } catch (e: any) {
    podMetrics.value = { items: [], total_request: {}, total_limit: {} }
  }
}

async function loadEvents() {
  eventsLoading.value = true
  try {
    const { resourceApi } = await import('@/api')
    const res = await resourceApi.events(props.clusterId)
    events.value = res.data.items || []
  } catch (e: any) {
    events.value = []
  } finally {
    eventsLoading.value = false
  }
}

async function loadTopPods() {
  topPodsLoading.value = true
  try {
    const { analysisApi } = await import('@/api')
    const res = await analysisApi.getTopPods(props.clusterId, 5, 'cpu')
    topPods.value = res.data
  } catch (e: any) {
    topPods.value = { cpu_top: [], memory_top: [] }
  } finally {
    topPodsLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadOverview(), loadPodMetrics(), loadEvents(), loadTopPods()])
  } catch (e: any) {
    error.value = e.message || 'Load failed'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null || bytes === 0) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<style scoped>
.dashboard {
  padding: 0;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem;
  text-align: center;
}
.stat-card-running {
  border-color: var(--success);
}
.stat-card-pending {
  border-color: var(--warning);
}
.stat-card-failed {
  border-color: var(--error);
}
.stat-card-succeeded {
  border-color: var(--success);
}
.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}
.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
  font-family: var(--font-mono);
}
.card-badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  margin-left: auto;
}
.card-badge.warning {
  background: rgba(230, 162, 60, 0.15);
  color: var(--warning);
}
.pod-resource-summary {
  display: flex;
  gap: 2rem;
}
.resource-column {
  flex: 1;
  min-width: 200px;
}
.resource-column-header {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.resource-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0;
}
.resource-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.resource-value {
  font-family: var(--font-mono);
  font-size: 0.85rem;
}
.text-muted {
  color: var(--text-muted);
}
.event-type {
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}
.event-normal {
  background: rgba(63, 185, 80, 0.15);
  color: var(--success);
}
.event-warning {
  background: rgba(230, 162, 60, 0.15);
  color: var(--warning);
}
.event-object {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.event-message {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-pods-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
.top-pods-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.top-pod-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  background: var(--bg-dark);
  border-radius: 6px;
}
.top-pod-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--border);
  color: var(--text-secondary);
}
.top-pod-rank.rank-1 {
  background: #ffd700;
  color: #000;
}
.top-pod-rank.rank-2 {
  background: #c0c0c0;
  color: #000;
}
.top-pod-rank.rank-3 {
  background: #cd7f32;
  color: #fff;
}
.top-pod-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}
.top-pod-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-pod-usage {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
</style>
