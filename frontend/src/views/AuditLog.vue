<template>
  <div class="audit-log-page">
    <div class="page-header">
      <div class="page-header-left">
        <!-- 过滤器 -->
        <select v-model="filterAction" class="form-control" @change="loadLogs">
          <option value="">全部操作</option>
          <option value="scale">扩缩容</option>
          <option value="delete">删除</option>
          <option value="create">创建</option>
          <option value="update">更新</option>
        </select>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" @click="loadLogs">刷新</button>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="card">
      <div class="card-body">
        <div v-if="loading" class="empty-state">加载中...</div>
        <div v-else-if="!logs.length" class="empty-state">暂无审计日志</div>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作者</th>
                <th>操作类型</th>
                <th>资源类型</th>
                <th>资源名称</th>
                <th>命名空间</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.id">
                <td>{{ formatTime(log.timestamp) }}</td>
                <td>{{ log.operator }}</td>
                <td>
                  <span class="action-badge" :class="'action-' + log.action">
                    {{ getActionLabel(log.action) }}
                  </span>
                </td>
                <td>{{ log.resource_type }}</td>
                <td class="resource-name">{{ log.namespace }}/{{ log.resource_name }}</td>
                <td>{{ log.namespace || '-' }}</td>
                <td class="details-cell">
                  <pre v-if="log.details" class="details-pre">{{ formatDetails(log.details) }}</pre>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > limit" class="pagination">
      <button
        class="btn btn-sm btn-secondary"
        :disabled="offset === 0"
        @click="changePage(-1)"
      >
        上一页
      </button>
      <span class="page-info">{{ offset + 1 }} - {{ Math.min(offset + limit, total) }} / {{ total }}</span>
      <button
        class="btn btn-sm btn-secondary"
        :disabled="offset + limit >= total"
        @click="changePage(1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { auditApi } from '@/api'

const logs = ref<any[]>([])
const loading = ref(true)
const total = ref(0)
const limit = ref(50)
const offset = ref(0)
const filterAction = ref('')

async function loadLogs() {
  loading.value = true
  try {
    const res = await auditApi.getAuditLogs(undefined, limit.value)
    logs.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('加载审计日志失败:', e)
    logs.value = []
  } finally {
    loading.value = false
  }
}

function changePage(delta: number) {
  offset.value = Math.max(0, offset.value + delta * limit.value)
  loadLogs()
}

function formatTime(timestamp: string): string {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function getActionLabel(action: string): string {
  const map: Record<string, string> = {
    scale: '扩缩容',
    delete: '删除',
    create: '创建',
    update: '更新',
    restart: '重启',
  }
  return map[action] || action
}

function formatDetails(details: any): string {
  if (typeof details === 'string') {
    try {
      details = JSON.parse(details)
    } catch {}
  }
  return JSON.stringify(details, null, 2)
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.audit-log-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.page-header-left .form-control {
  width: auto;
  min-width: 150px;
}

.action-badge {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}

.action-scale {
  background: rgba(63, 185, 80, 0.15);
  color: var(--success);
}

.action-delete {
  background: rgba(248, 81, 73, 0.15);
  color: var(--error);
}

.action-create {
  background: rgba(88, 166, 255, 0.15);
  color: var(--accent);
}

.action-update {
  background: rgba(210, 153, 34, 0.15);
  color: var(--warning);
}

.resource-name {
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.details-cell {
  max-width: 200px;
}

.details-pre {
  margin: 0;
  padding: 0.25rem;
  background: var(--bg-dark);
  border-radius: 4px;
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre-wrap;
  word-break: break-all;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}

.page-info {
  font-size: 0.9rem;
  color: var(--text-muted);
}
</style>
