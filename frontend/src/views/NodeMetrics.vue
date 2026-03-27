<template>
  <div class="node-metrics">
    <div v-if="loading" class="empty-state">Loading...</div>
    <div v-else-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>
    <template v-else-if="nodeMetrics && nodeMetrics.items">
      <!-- 汇总卡片 -->
      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-label">节点数</div>
          <div class="stat-value">{{ nodeMetrics.items.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">CPU 总量</div>
          <div class="stat-value">{{ totalCpu }} Cores</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">CPU 使用</div>
          <div class="stat-value">{{ usedCpu }} Cores</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">内存总量</div>
          <div class="stat-value">{{ formatBytes(totalMemory) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">内存使用</div>
          <div class="stat-value">{{ formatBytes(usedMemory) }}</div>
        </div>
      </div>

      <!-- 节点详情 -->
      <div class="card" style="margin-top: 1.5rem">
        <div class="card-header">
          <span class="card-title">节点详情</span>
        </div>
        <div class="card-body">
          <div v-if="!nodeMetrics.items.length" class="empty-state">暂无节点数据</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>节点名称</th>
                  <th>IP</th>
                  <th>CPU Request</th>
                  <th>CPU Limit</th>
                  <th>CPU Usage</th>
                  <th>Memory Request</th>
                  <th>Memory Limit</th>
                  <th>Memory Usage</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="node in nodeMetrics.items" :key="node.name">
                  <td class="node-name">{{ node.name }}</td>
                  <td>{{ node.ip || '-' }}</td>
                  <td>{{ node.cpu_request ? node.cpu_request + ' Cores' : '-' }}</td>
                  <td>{{ node.cpu_limit ? node.cpu_limit + ' Cores' : '-' }}</td>
                  <td>
                    <span v-if="node.cpu_usage && node.cpu_limit" class="usage-value" :class="getUsageClass(node.cpu_usage, node.cpu_limit)">
                      {{ node.cpu_usage }} Cores ({{ getCpuPercent(node.cpu_usage, node.cpu_limit) }}%)
                    </span>
                    <span v-else>-</span>
                  </td>
                  <td>{{ formatBytes(node.memory_request) }}</td>
                  <td>{{ formatBytes(node.memory_limit) }}</td>
                  <td>
                    <span v-if="node.memory_usage && node.memory_limit" class="usage-value" :class="getUsageClass(node.memory_usage, node.memory_limit)">
                      {{ formatBytes(node.memory_usage) }} ({{ getMemPercent(node.memory_usage, node.memory_limit) }}%)
                    </span>
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
    <div v-else-if="nodeMetrics" class="empty-state">暂无节点数据</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const props = defineProps<{
  clusterId: number
}>()

const nodeMetrics = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function loadNodeMetrics() {
  loading.value = true
  error.value = ''
  try {
    const { resourceApi } = await import('@/api')
    const res = await resourceApi.metricsNodes(props.clusterId)
    nodeMetrics.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || 'Load failed'
  } finally {
    loading.value = false
  }
}

onMounted(loadNodeMetrics)

const totalCpu = computed(() => {
  if (!nodeMetrics.value?.items) return 0
  return nodeMetrics.value.items.reduce((sum: number, n: any) => sum + (n.cpu_request || 0), 0).toFixed(2)
})

const usedCpu = computed(() => {
  if (!nodeMetrics.value?.items) return 0
  return nodeMetrics.value.items.reduce((sum: number, n: any) => sum + (n.cpu_usage || 0), 0).toFixed(2)
})

const totalMemory = computed(() => {
  if (!nodeMetrics.value?.items) return 0
  return nodeMetrics.value.items.reduce((sum: number, n: any) => sum + (n.memory_request || 0), 0)
})

const usedMemory = computed(() => {
  if (!nodeMetrics.value?.items) return 0
  return nodeMetrics.value.items.reduce((sum: number, n: any) => sum + (n.memory_usage || 0), 0)
})

function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null || bytes === 0) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function getCpuPercent(usage: number, limit: number): string {
  if (!limit) return '0'
  return ((usage / limit) * 100).toFixed(1)
}

function getMemPercent(usage: number, limit: number): string {
  if (!limit) return '0'
  return ((usage / limit) * 100).toFixed(1)
}

function getUsageClass(usage: number, limit: number): string {
  if (!limit) return ''
  const percent = (usage / limit) * 100
  if (percent >= 90) return 'usage-critical'
  if (percent >= 70) return 'usage-warning'
  return 'usage-normal'
}
</script>

<style scoped>
.node-metrics {
  padding: 0;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem;
  text-align: center;
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
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
th, td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th {
  font-weight: 500;
  color: var(--text-muted);
  font-size: 0.8rem;
}
.node-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.usage-value {
  font-family: var(--font-mono);
}
.usage-normal {
  color: var(--success);
}
.usage-warning {
  color: var(--warning);
}
.usage-critical {
  color: var(--error);
}
</style>
