<template>
  <div class="dashboard">
    <div v-if="loading" class="empty-state">加载中...</div>
    <div v-else-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>
    <template v-else-if="metrics">
      <!-- 统计卡片 -->
      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-label">集群节点</div>
          <div class="stat-value">{{ metrics.node_count }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">命名空间</div>
          <div class="stat-value">{{ metrics.namespace_count }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Pod 总数</div>
          <div class="stat-value">{{ metrics.pod_stats.total }}</div>
        </div>
        <div class="stat-card stat-card-running">
          <div class="stat-label">Pod 运行中</div>
          <div class="stat-value">{{ metrics.pod_stats.running }}</div>
        </div>
        <div class="stat-card stat-card-pending">
          <div class="stat-label">Pod 等待中</div>
          <div class="stat-value">{{ metrics.pod_stats.pending }}</div>
        </div>
        <div class="stat-card stat-card-failed">
          <div class="stat-label">Pod 异常</div>
          <div class="stat-value">{{ metrics.pod_stats.failed }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Deployment</div>
          <div class="stat-value">{{ metrics.deployment_count }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">StatefulSet</div>
          <div class="stat-value">{{ metrics.statefulset_count }}</div>
        </div>
      </div>

      <!-- 资源使用量 -->
      <div class="card" style="margin-top: 1.5rem">
        <div class="card-header">
          <span class="card-title">资源使用量</span>
          <span v-if="!metrics.metrics_available" class="card-badge warning">metrics-server 未安装或不可用</span>
        </div>
        <div class="card-body">
          <div class="resource-metrics">
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">节点 CPU 使用</span>
                <span class="metric-value">{{ metrics.cpu_usage }} Cores</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">节点内存 使用</span>
                <span class="metric-value">{{ formatBytes(metrics.memory_usage) }}</span>
              </div>
            </div>
          </div>
          <div v-if="!metrics.metrics_available" class="empty-state" style="margin-top: 1rem">
            请确保集群已安装 metrics-server，执行 <code>kubectl top nodes</code> 验证
          </div>
        </div>
      </div>

      <!-- Pod 资源请求量 -->
      <div class="card" style="margin-top: 1.5rem">
        <div class="card-header">
          <span class="card-title">Pod 资源请求量</span>
        </div>
        <div class="card-body">
          <div class="resource-metrics">
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">CPU 请求量</span>
                <span class="metric-value">{{ metrics.pod_cpu_request }} Cores</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">CPU Limit 量</span>
                <span class="metric-value">{{ metrics.pod_cpu_limit }} Cores</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">内存 请求量</span>
                <span class="metric-value">{{ formatBytes(metrics.pod_memory_request) }}</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-label">内存 Limit 量</span>
                <span class="metric-value">{{ formatBytes(metrics.pod_memory_limit) }}</span>
              </div>
            </div>
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

const metrics = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function loadMetrics() {
  loading.value = true
  error.value = ''
  try {
    const { resourceApi } = await import('@/api')
    const res = await resourceApi.metrics(props.clusterId)
    metrics.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadMetrics)

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
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
.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}
.stat-value {
  font-size: 2rem;
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
.resource-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.5rem;
}
.metric-item {
  padding: 0.5rem 0;
}
.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.metric-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.metric-value {
  font-family: var(--font-mono);
  font-size: 0.85rem;
}
</style>
