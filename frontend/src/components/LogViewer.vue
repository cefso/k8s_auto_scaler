<template>
  <div class="log-viewer">
    <!-- 日志工具栏 -->
    <div class="log-toolbar">
      <div class="log-toolbar-left">
        <span class="log-title">日志 - {{ namespace }}/{{ podName }}</span>
        <select v-if="containers.length > 1" v-model="selectedContainer" class="form-control container-select">
          <option v-for="c in containers" :key="c.name" :value="c.name">{{ c.name }}</option>
        </select>
      </div>
      <div class="log-toolbar-right">
        <label class="auto-scroll-toggle">
          <input type="checkbox" v-model="autoScroll" />
          自动滚动
        </label>
        <input
          v-model="searchKeyword"
          type="text"
          class="form-control search-input"
          placeholder="搜索关键词"
        />
        <button class="btn btn-sm btn-secondary" @click="downloadLogs">下载日志</button>
        <button class="btn btn-sm btn-secondary" @click="clearLogs">清屏</button>
        <button
          class="btn btn-sm"
          :class="isPaused ? 'btn-primary' : 'btn-secondary'"
          @click="togglePause"
        >
          {{ isPaused ? '继续' : '暂停' }}
        </button>
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">关闭</button>
      </div>
    </div>

    <!-- 日志内容 -->
    <div class="log-content" ref="logContentRef">
      <div v-if="loading" class="log-loading">加载中...</div>
      <div v-else-if="error" class="log-error">{{ error }}</div>
      <div v-else-if="!logs.length && !isConnected" class="log-empty">暂无日志</div>
      <template v-else>
        <div
          v-for="(log, index) in filteredLogs"
          :key="index"
          class="log-line"
          :class="{ 'highlighted': isHighlighted(log) }"
          v-html="highlightKeyword(log)"
        ></div>
      </template>
      <div v-if="isConnected && !isPaused" class="log-connecting">
        <span class="pulse"></span> 实时接收日志中...
      </div>
      <div v-if="isPaused" class="log-paused">已暂停接收新日志</div>
    </div>

    <!-- 状态栏 -->
    <div class="log-status">
      <span>共 {{ logs.length }} 行</span>
      <span v-if="searchKeyword"> | 匹配 {{ filteredLogs.length }} 行</span>
      <span> | {{ isConnected ? '已连接' : '未连接' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

interface LogMessage {
  type: 'log' | 'error' | 'done'
  content: string
}

interface Container {
  name: string
  image: string
}

const props = defineProps<{
  clusterId: number
  namespace: string
  podName: string
  container?: string
}>()

const emit = defineEmits<{
  close: []
}>()

// 状态
const logs = ref<string[]>([])
const loading = ref(true)
const error = ref('')
const isConnected = ref(false)
const isPaused = ref(false)
const autoScroll = ref(true)
const searchKeyword = ref('')
const containers = ref<Container[]>([])
const selectedContainer = ref(props.container || '')
const logContentRef = ref<HTMLElement | null>(null)
let ws: WebSocket | null = null
let reconnectTimer: number | null = null

// 计算属性
const filteredLogs = computed(() => {
  if (!searchKeyword.value) return logs.value
  const keyword = searchKeyword.value.toLowerCase()
  return logs.value.filter(log => log.toLowerCase().includes(keyword))
})

// 方法
function isHighlighted(log: string): boolean {
  if (!searchKeyword.value) return false
  return log.toLowerCase().includes(searchKeyword.value.toLowerCase())
}

function highlightKeyword(log: string): string {
  if (!searchKeyword.value) return escapeHtml(log)
  const keyword = searchKeyword.value
  const regex = new RegExp(`(${escapeRegex(keyword)})`, 'gi')
  return escapeHtml(log).replace(regex, '<mark class="highlight">$1</mark>')
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function escapeRegex(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function togglePause() {
  isPaused.value = !isPaused.value
}

function clearLogs() {
  logs.value = []
}

function downloadLogs() {
  const content = filteredLogs.value.join('\n')
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${props.podName}-${selectedContainer.value || 'all'}-${Date.now()}.log`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function scrollToBottom() {
  if (logContentRef.value && autoScroll.value) {
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
  }
}

function connectWebSocket() {
  if (ws) {
    ws.close()
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const params = new URLSearchParams({
    namespace: props.namespace,
    pod_name: props.podName,
    tail_lines: '100',
  })
  if (selectedContainer.value) {
    params.set('container', selectedContainer.value)
  }

  const wsUrl = `${protocol}//${host}/api/logs/ws/${props.clusterId}/pod?${params.toString()}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    isConnected.value = true
    error.value = ''
    loading.value = false
  }

  ws.onmessage = (event) => {
    try {
      const data: LogMessage = JSON.parse(event.data)

      if (data.type === 'log') {
        if (!isPaused.value) {
          logs.value.push(data.content)
          // 限制日志条数，避免内存溢出
          if (logs.value.length > 10000) {
            logs.value = logs.value.slice(-5000)
          }
          scrollToBottom()
        }
      } else if (data.type === 'error') {
        error.value = data.content
        loading.value = false
      } else if (data.type === 'done') {
        // 完成信号，可以忽略或显示
      }
    } catch (e) {
      console.error('解析日志消息失败:', e)
    }
  }

  ws.onclose = () => {
    isConnected.value = false
    // 尝试重连
    if (!reconnectTimer) {
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null
        if (!isPaused.value) {
          connectWebSocket()
        }
      }, 3000)
    }
  }

  ws.onerror = (e) => {
    console.error('WebSocket 错误:', e)
    error.value = 'WebSocket 连接错误'
    loading.value = false
  }
}

async function fetchContainers() {
  try {
    const res = await fetch(`/api/logs/${props.clusterId}/pod/containers?namespace=${props.namespace}&pod_name=${props.podName}`)
    if (res.ok) {
      const data = await res.json()
      containers.value = data.containers || []
      if (containers.value.length > 0 && !selectedContainer.value) {
        selectedContainer.value = containers.value[0].name
      }
    }
  } catch (e) {
    console.error('获取容器列表失败:', e)
  }
}

async function fetchInitialLogs() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      namespace: props.namespace,
      pod_name: props.podName,
      tail_lines: '500',
    })
    if (selectedContainer.value) {
      params.set('container', selectedContainer.value)
    }
    const res = await fetch(`/api/logs/${props.clusterId}/pod?${params.toString()}`)
    if (res.ok) {
      const data = await res.json()
      logs.value = data.logs.split('\n').filter((l: string) => l.trim())
    } else {
      error.value = '获取日志失败'
    }
  } catch (e: any) {
    error.value = e.message || '获取日志失败'
  } finally {
    loading.value = false
  }
}

// 监听容器切换
watch(selectedContainer, () => {
  if (ws) {
    ws.close()
  }
  logs.value = []
  fetchInitialLogs().then(() => {
    connectWebSocket()
  })
})

// 生命周期
onMounted(async () => {
  await fetchContainers()
  await fetchInitialLogs()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
  }
})
</script>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.log-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: var(--bg-dark);
  border-bottom: 1px solid var(--border);
  gap: 1rem;
  flex-wrap: wrap;
}

.log-toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.log-toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.log-title {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-primary);
}

.container-select {
  width: auto;
  min-width: 120px;
  font-size: 0.85rem;
}

.auto-scroll-toggle {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
}

.auto-scroll-toggle input {
  cursor: pointer;
}

.search-input {
  width: 150px;
  font-size: 0.85rem;
}

.log-content {
  flex: 1;
  overflow: auto;
  padding: 0.5rem 1rem;
  background: var(--bg-dark);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-line {
  padding: 0.1rem 0;
  color: var(--text-primary);
}

.log-line.highlighted {
  background: rgba(255, 255, 0, 0.1);
}

.log-line :deep(.highlight) {
  background: rgba(255, 200, 0, 0.4);
  padding: 0 2px;
  border-radius: 2px;
}

.log-loading,
.log-error,
.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
}

.log-error {
  color: var(--error);
}

.log-connecting {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--success);
  padding: 0.5rem 0;
}

.log-paused {
  color: var(--warning);
  padding: 0.5rem 0;
}

.pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}

.log-status {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--bg-dark);
  border-top: 1px solid var(--border);
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
