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
              <th>操作</th>
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
              <td>
                <div class="action-buttons">
                  <button class="btn btn-sm btn-secondary" @click="openLogViewer(pod)">日志</button>
                  <button class="btn btn-sm btn-secondary" @click="openPodEvents(pod)">事件</button>
                </div>
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

    <!-- Pod 事件弹窗 -->
    <div v-if="showEventsModal" class="modal-overlay" @click.self="showEventsModal = false">
      <div class="modal modal-events">
        <div class="modal-header">
          <h2>Pod 事件 - {{ eventsPodName }}</h2>
          <button class="btn btn-sm btn-secondary" @click="showEventsModal = false">关闭</button>
        </div>
        <div v-if="eventsLoading" class="empty-state">加载中...</div>
        <div v-else-if="!podEvents.length" class="empty-state">暂无事件</div>
        <div v-else class="events-timeline">
          <div
            v-for="(event, index) in podEvents"
            :key="index"
            class="timeline-item"
            :class="{ 'timeline-warning': event.type === 'Warning' }"
          >
            <div class="timeline-marker">
              <div class="timeline-dot" :class="event.type === 'Warning' ? 'dot-warning' : 'dot-normal'"></div>
              <div v-if="index < podEvents.length - 1" class="timeline-line"></div>
            </div>
            <div class="timeline-content">
              <div class="event-header">
                <span class="event-type" :class="event.type === 'Warning' ? 'type-warning' : 'type-normal'">
                  {{ event.type }}
                </span>
                <span class="event-reason">{{ event.reason }}</span>
                <span class="event-time">{{ event.last_timestamp || event.age }}</span>
              </div>
              <div class="event-message">{{ event.message }}</div>
              <div class="event-source">来源: {{ event.source || '-' }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 日志查看弹窗 -->
    <div v-if="showLogViewer" class="modal-overlay" @click.self="showLogViewer = false">
      <div class="modal modal-log">
        <div class="modal-header">
          <h2>日志查看</h2>
          <button class="btn btn-sm btn-secondary" @click="showLogViewer = false">关闭</button>
        </div>
        <LogViewer
          v-if="showLogViewer"
          :cluster-id="clusterId"
          :namespace="logPodNamespace"
          :pod-name="logPodName"
          @close="showLogViewer = false"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resourceApi } from '@/api'
import LogViewer from '@/components/LogViewer.vue'

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

// 日志相关
const showLogViewer = ref(false)
const logPodName = ref('')
const logPodNamespace = ref('')

// 事件相关
const showEventsModal = ref(false)
const eventsPodName = ref('')
const eventsPodNamespace = ref('')
const podEvents = ref<any[]>([])
const eventsLoading = ref(false)

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

function openLogViewer(pod: any) {
  logPodName.value = pod.name
  logPodNamespace.value = namespace.value
  showLogViewer.value = true
}

async function openPodEvents(pod: any) {
  eventsPodName.value = pod.name
  eventsPodNamespace.value = namespace.value
  showEventsModal.value = true
  eventsLoading.value = true
  podEvents.value = []
  try {
    const res = await resourceApi.getPodEvents(
      clusterId.value,
      namespace.value,
      pod.name
    )
    podEvents.value = res.data.items || []
  } catch (e: any) {
    console.error('获取 Pod 事件失败:', e)
    podEvents.value = []
  } finally {
    eventsLoading.value = false
  }
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
.modal-log {
  max-width: 95vw;
  width: 1200px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}
.modal-events {
  max-width: 90vw;
  width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.events-timeline {
  flex: 1;
  overflow: auto;
  padding: 1rem;
}
.timeline-item {
  display: flex;
  gap: 1rem;
  padding-bottom: 1rem;
}
.timeline-item:last-child {
  padding-bottom: 0;
}
.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
.timeline-dot.dot-normal {
  background: var(--accent);
  border: 2px solid var(--accent);
}
.timeline-dot.dot-warning {
  background: var(--error);
  border: 2px solid var(--error);
  box-shadow: 0 0 0 4px rgba(248, 81, 73, 0.2);
}
.timeline-line {
  width: 2px;
  flex: 1;
  background: var(--border);
  margin-top: 4px;
}
.timeline-content {
  flex: 1;
  min-width: 0;
}
.timeline-warning .timeline-content {
  background: rgba(248, 81, 73, 0.05);
  border-radius: 6px;
  padding: 0.75rem;
  border-left: 3px solid var(--error);
}
.event-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.event-type {
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}
.event-type.type-normal {
  background: var(--success);
  color: white;
}
.event-type.type-warning {
  background: var(--error);
  color: white;
}
.event-reason {
  font-weight: 500;
  color: var(--text);
}
.event-time {
  color: var(--text-muted);
  font-size: 0.85rem;
}
.event-message {
  color: var(--text);
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  word-break: break-all;
}
.event-source {
  color: var(--text-muted);
  font-size: 0.8rem;
}
.action-buttons {
  display: flex;
  gap: 0.35rem;
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
