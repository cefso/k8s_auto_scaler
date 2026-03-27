<template>
  <div>
    <div class="page-header">
      <div class="page-title">
        <h1>{{ workloadKind }}: {{ namespace }}/{{ workloadName }}</h1>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" @click="goBack">返回</button>
        <button class="btn btn-secondary" @click="viewYaml">查看 YAML</button>
        <button class="btn btn-secondary" @click="refreshPods">刷新</button>
      </div>
    </div>

    <!-- 工作负载基本信息卡片 -->
    <div v-if="workload" class="workload-info">
      <div class="info-card info-card-wide">
        <div class="info-card-label">镜像</div>
        <div class="info-card-value image-list">{{ workload.images?.join(', ') }}</div>
      </div>
      <div class="info-cards-row">
        <div class="info-card">
          <div class="info-card-label">类型</div>
          <div class="info-card-value">{{ workload.kind }}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">副本数</div>
          <div class="info-card-value">{{ workload.ready_replicas || 0 }} / {{ workload.replicas }}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">CPU 限制</div>
          <div class="info-card-value">{{ workload.cpu_limit != null ? `${workload.cpu_limit} Cores` : '-' }}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">内存限制</div>
          <div class="info-card-value">{{ workload.memory_limit != null ? formatBytes(workload.memory_limit) : '-' }}</div>
        </div>
      </div>
    </div>

    <!-- Pod 列表卡片 -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">Pod 列表 ({{ pods.length }})</span>
      </div>
      <div v-if="loading" class="empty-state">加载中...</div>
      <div v-else-if="!pods.length" class="empty-state">暂无 Pod</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Pod 名称</th>
              <th>状态</th>
              <th>Ready</th>
              <th>重启</th>
              <th>CPU Request</th>
              <th>CPU Limit</th>
              <th>CPU Usage</th>
              <th>Memory Request</th>
              <th>Memory Limit</th>
              <th>Memory Usage</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pod in pods" :key="pod.name">
              <td>{{ pod.name }}</td>
              <td>{{ pod.phase }}</td>
              <td>{{ pod.ready }}</td>
              <td>{{ pod.restarts }}</td>
              <td>{{ pod.cpu_request != null ? `${pod.cpu_request} Cores` : '-' }}</td>
              <td>{{ pod.cpu_limit != null ? `${pod.cpu_limit} Cores` : '-' }}</td>
              <td :class="getUsageClass(pod.cpu_usage, pod.cpu_limit)">
                {{ pod.cpu_usage != null ? `${pod.cpu_usage} Cores` : '-' }}
              </td>
              <td>{{ formatBytes(pod.memory_request) }}</td>
              <td>{{ formatBytes(pod.memory_limit) }}</td>
              <td :class="getUsageClass(pod.memory_usage, pod.memory_limit)">
                {{ pod.memory_usage != null ? formatBytes(pod.memory_usage) : '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- YAML 弹窗 -->
    <div v-if="showYamlModal" class="modal-overlay" @click.self="showYamlModal = false">
      <div class="modal modal-yaml">
        <div class="modal-header">
          <h2>{{ workloadKind }} YAML</h2>
          <div class="modal-header-actions">
            <button v-if="hasCollapsedFields" class="btn btn-sm btn-secondary" @click="toggleYamlFields">
              {{ showCollapsedFields ? '折叠冗余字段' : '显示全部字段' }}
            </button>
            <button class="btn btn-sm btn-secondary" @click="showYamlModal = false">关闭</button>
          </div>
        </div>
        <pre v-if="yamlLoading" class="yaml-content">加载中...</pre>
        <pre v-else class="yaml-content">{{ displayYaml }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resourceApi } from '@/api'

const route = useRoute()
const router = useRouter()

const clusterId = computed(() => Number(route.params.clusterId))
const workloadKind = computed(() => route.query.kind as string)
const namespace = computed(() => route.query.namespace as string)
const workloadName = computed(() => route.query.name as string)

const workload = ref<any>(null)
const pods = ref<any[]>([])
const loading = ref(true)

// YAML 相关
const showYamlModal = ref(false)
const yamlContent = ref('')
const yamlRawContent = ref('')
const yamlLoading = ref(false)
const showCollapsedFields = ref(false)

const hasCollapsedFields = computed(() => {
  const raw = yamlRawContent.value
  if (!raw) return false
  const pattern = /^\s*(managedFields|status):\s*$/m
  return pattern.test(raw)
})

const displayYaml = computed(() => {
  if (showCollapsedFields.value) {
    return yamlRawContent.value
  }
  return yamlContent.value
})

function getUsageClass(usage: number | null, limit: number | null): string {
  if (usage == null || limit == null || limit === 0) return ''
  const percent = (usage / limit) * 100
  if (percent < 70) return 'usage-low'
  if (percent < 90) return 'usage-medium'
  return 'usage-high'
}

function formatBytes(bytes: number | null): string {
  if (bytes == null) return '-'
  if (bytes === 0) return '0'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`
}

function goBack() {
  router.back()
}

async function loadPods() {
  loading.value = true
  try {
    const res = await resourceApi.workloadPods(
      clusterId.value,
      namespace.value,
      workloadKind.value,
      workloadName.value
    )
    workload.value = res.data.workload
    pods.value = res.data.items
  } catch (e) {
    workload.value = null
    pods.value = []
  } finally {
    loading.value = false
  }
}

async function refreshPods() {
  await loadPods()
}

async function viewYaml() {
  showYamlModal.value = true
  yamlContent.value = ''
  yamlRawContent.value = ''
  yamlLoading.value = true
  showCollapsedFields.value = false
  try {
    const res = await resourceApi.getYaml(
      clusterId.value,
      workloadKind.value.toLowerCase() + 's',
      namespace.value,
      workloadName.value
    )
    yamlRawContent.value = res.data.yaml
    yamlContent.value = collapseYamlFields(res.data.yaml)
  } catch (e: any) {
    yamlContent.value = '加载失败: ' + (e.response?.data?.detail || e.message)
    yamlRawContent.value = ''
  } finally {
    yamlLoading.value = false
  }
}

function toggleYamlFields() {
  showCollapsedFields.value = !showCollapsedFields.value
}

function collapseYamlFields(yaml: string): string {
  const lines = yaml.split('\n')
  const result: string[] = []
  const fieldsToCollapse = ['managedFields', 'status']

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.trim() === '') {
      result.push(line)
      continue
    }

    const fieldMatch = line.match(/^(\s*)(\w+):\s*$/)
    if (fieldMatch) {
      const fieldIndent = fieldMatch[1].length
      const fieldName = fieldMatch[2]

      if (fieldsToCollapse.includes(fieldName)) {
        result.push(`${fieldMatch[1]}# --- ${fieldName} 已折叠 ---`)

        i++
        let contentIndent: number | null = null
        let isArray = false

        while (i < lines.length) {
          const currentLine = lines[i]

          if (currentLine.trim() === '') {
            i++
            continue
          }

          const currentIndent = currentLine.search(/\S/)

          if (contentIndent === null) {
            contentIndent = currentIndent
            isArray = currentLine.trim().startsWith('-')
          }

          if (isArray) {
            if (currentIndent <= contentIndent - 1) {
              break
            }
            if (currentIndent === contentIndent && !currentLine.trim().startsWith('-')) {
              break
            }
          } else {
            if (currentIndent <= fieldIndent) {
              break
            }
          }

          i++
        }
        continue
      }
    }

    result.push(line)
  }

  return result.join('\n')
}

onMounted(() => {
  loadPods()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.page-header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.card-title {
  font-weight: 500;
  font-size: 0.95rem;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  width: 90%;
  max-width: 400px;
}
.modal-yaml {
  max-width: 90vw;
  width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.modal-header h2 {
  margin: 0;
  font-size: 1rem;
  font-family: var(--font-mono);
}
.modal-header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.yaml-content {
  flex: 1;
  overflow: auto;
  padding: 1rem;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  margin: 0;
}
.usage-low {
  color: var(--success);
}
.usage-medium {
  color: var(--warning);
}
.usage-high {
  color: var(--error);
}
.workload-info {
  margin-bottom: 1rem;
}
.workload-info .info-card-wide {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}
.info-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
.info-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
}
.info-card-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}
.info-card-value {
  font-size: 1rem;
  font-weight: 500;
}
.info-card .image-list {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  word-break: break-all;
}
</style>
