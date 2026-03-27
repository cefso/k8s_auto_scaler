<template>
  <div class="node-metrics">
    <div v-if="loading" class="empty-state">Loading...</div>
    <div v-else-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>
    <div v-else-if="nodeMetrics && nodeMetrics.items" class="stat-cards">
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
</style>
