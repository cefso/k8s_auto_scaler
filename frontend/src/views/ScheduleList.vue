<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">定时扩缩容</h1>
      <button class="btn btn-primary" @click="showAddModal = true">新建任务</button>
    </div>

    <div class="card" v-if="schedules.length">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>集群</th>
              <th>资源</th>
              <th>目标副本</th>
              <th>cron 表达式</th>
              <th>时区</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in schedules" :key="s.id">
              <td>{{ clusterMap[s.cluster_id] || `#${s.cluster_id}` }}</td>
              <td>
                <code>{{ s.namespace }}/{{ s.resource_name }}</code>
                <span class="badge badge-default" style="margin-left:4px">{{ s.resource_type }}</span>
              </td>
              <td>{{ s.target_replicas }}</td>
              <td><code>{{ s.cron_expression }}</code></td>
              <td>{{ s.timezone }}</td>
              <td>
                <span :class="['badge', s.is_enabled ? 'badge-success' : 'badge-default']">
                  {{ s.is_enabled ? '启用' : '禁用' }}
                </span>
              </td>
              <td>
                <button class="btn btn-sm btn-secondary" @click="editSchedule(s)">编辑</button>
                <button class="btn btn-sm btn-danger" @click="deleteSchedule(s)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" v-else>
      <div class="empty-state">
        <p>暂无定时任务，点击「新建任务」添加扩缩容计划</p>
        <p class="hint">示例：工作日 9:00 扩容、18:00 缩容</p>
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal modal-wide">
        <h2>{{ editingId ? '编辑任务' : '新建任务' }}</h2>
        <form @submit.prevent="saveSchedule">
          <div class="form-group">
            <label>集群 *</label>
            <select v-model="form.cluster_id" class="form-control" required>
              <option value="">请选择</option>
              <option v-for="c in clusters" :key="c.id" :value="c.id">
                {{ c.display_name || c.name }}
              </option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>命名空间 *</label>
              <input v-model="form.namespace" class="form-control" placeholder="default" required />
            </div>
            <div class="form-group">
              <label>资源类型</label>
              <select v-model="form.resource_type" class="form-control">
                <option value="Deployment">Deployment</option>
                <option value="StatefulSet">StatefulSet</option>
              </select>
            </div>
            <div class="form-group">
              <label>资源名称 *</label>
              <input v-model="form.resource_name" class="form-control" required />
            </div>
          </div>
          <div class="form-group">
            <label>目标副本数 *</label>
            <input v-model.number="form.target_replicas" type="number" min="0" class="form-control" required />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Cron 表达式 *</label>
              <input v-model="form.cron_expression" class="form-control" placeholder="0 9 * * 1-5" required />
              <small class="form-hint">例: 0 9 * * 1-5 = 周一至五 9:00</small>
            </div>
            <div class="form-group">
              <label>时区</label>
              <input v-model="form.timezone" class="form-control" placeholder="Asia/Shanghai" />
            </div>
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="form.description" class="form-control" placeholder="可选" />
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.is_enabled" />
              启用
            </label>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showAddModal = false">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="loading">保存</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { clusterApi, scalingApi } from '@/api'
import type { Cluster, ScalingSchedule } from '@/api'

const schedules = ref<ScalingSchedule[]>([])
const clusters = ref<Cluster[]>([])
const clusterMap = computed(() => {
  const m: Record<number, string> = {}
  clusters.value.forEach((c) => (m[c.id] = c.display_name || c.name))
  return m
})

const showAddModal = ref(false)
const editingId = ref<number | null>(null)
const loading = ref(false)
const form = ref({
  cluster_id: null as number | null,
  namespace: '',
  resource_type: 'Deployment',
  resource_name: '',
  target_replicas: 0,
  cron_expression: '0 9 * * 1-5',
  timezone: 'Asia/Shanghai',
  description: '',
  is_enabled: true,
})

async function loadSchedules() {
  const res = await scalingApi.listSchedules()
  schedules.value = res.data
}

async function loadClusters() {
  const res = await clusterApi.list()
  clusters.value = res.data
}

function editSchedule(s: ScalingSchedule) {
  editingId.value = s.id
  form.value = {
    cluster_id: s.cluster_id,
    namespace: s.namespace,
    resource_type: s.resource_type,
    resource_name: s.resource_name,
    target_replicas: s.target_replicas,
    cron_expression: s.cron_expression,
    timezone: s.timezone,
    description: s.description || '',
    is_enabled: s.is_enabled,
  }
  showAddModal.value = true
}

function resetForm() {
  editingId.value = null
  form.value = {
    cluster_id: null,
    namespace: '',
    resource_type: 'Deployment',
    resource_name: '',
    target_replicas: 0,
    cron_expression: '0 9 * * 1-5',
    timezone: 'Asia/Shanghai',
    description: '',
    is_enabled: true,
  }
}

async function saveSchedule() {
  if (form.value.cluster_id == null) return
  loading.value = true
  try {
    if (editingId.value) {
      await scalingApi.updateSchedule(editingId.value, {
        target_replicas: form.value.target_replicas,
        cron_expression: form.value.cron_expression,
        timezone: form.value.timezone,
        description: form.value.description,
        is_enabled: form.value.is_enabled,
      })
    } else {
      await scalingApi.createSchedule(form.value as any)
    }
    showAddModal.value = false
    resetForm()
    loadSchedules()
  } catch (e: any) {
    alert(e.response?.data?.detail || '保存失败')
  } finally {
    loading.value = false
  }
}

async function deleteSchedule(s: ScalingSchedule) {
  if (!confirm(`确定删除任务: ${s.namespace}/${s.resource_name}?`)) return
  try {
    await scalingApi.deleteSchedule(s.id)
    loadSchedules()
  } catch (e: any) {
    alert('删除失败')
  }
}

onMounted(() => {
  loadClusters()
  loadSchedules()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
code {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  background: var(--bg-dark);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}
.hint {
  font-size: 0.9rem;
  margin-top: 0.5rem;
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
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-wide {
  max-width: 560px;
}
.modal h2 {
  margin-bottom: 1rem;
  font-size: 1.25rem;
}
.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
}
.form-hint {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
