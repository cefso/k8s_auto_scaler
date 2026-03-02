<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">集群管理</h1>
      <button class="btn btn-primary" @click="showAddModal = true">
        添加集群
      </button>
    </div>

    <div class="card" v-if="clusters.length">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>名称</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in clusters" :key="c.id">
              <td>
                <router-link :to="`/cluster/${c.id}`" class="link">
                  {{ c.display_name || c.name }}
                </router-link>
              </td>
              <td>
                <span :class="['badge', c.is_active ? 'badge-success' : 'badge-default']">
                  {{ c.is_active ? '启用' : '禁用' }}
                </span>
              </td>
              <td>
                <div class="action-buttons">
                  <button class="btn btn-sm btn-secondary" @click="testConnection(c)">测试连接</button>
                  <router-link :to="`/cluster/${c.id}`" class="btn btn-sm btn-primary">查看</router-link>
                  <button class="btn btn-sm btn-danger" @click="confirmDelete(c)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" v-else>
      <div class="empty-state">
        <p>暂无集群，点击「添加集群」上传 kubeconfig 文件</p>
      </div>
    </div>

    <!-- 添加集群弹窗 -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h2>添加集群</h2>
        <form @submit.prevent="addCluster">
          <div class="form-group">
            <label>集群名称 *</label>
            <input v-model="form.name" class="form-control" placeholder="如: prod-cluster" required />
          </div>
          <div class="form-group">
            <label>显示名称</label>
            <input v-model="form.display_name" class="form-control" placeholder="可选" />
          </div>
          <div class="form-group">
            <label>Kubeconfig 内容 *</label>
            <textarea
              v-model="form.kubeconfig_content"
              class="form-control"
              placeholder="粘贴 kubeconfig 文件内容 (YAML)"
              required
            ></textarea>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showAddModal = false">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="loading">添加</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { clusterApi, type Cluster } from '@/api'
import { useClusterStore } from '@/stores/cluster'

const clusterStore = useClusterStore()
const clusters = computed(() => clusterStore.clusters)
const showAddModal = ref(false)
const loading = ref(false)
const form = ref({
  name: '',
  display_name: '',
  kubeconfig_content: '',
})

async function loadClusters() {
  await clusterStore.fetchClusters()
}

async function addCluster() {
  loading.value = true
  try {
    await clusterApi.create(form.value)
    showAddModal.value = false
    form.value = { name: '', display_name: '', kubeconfig_content: '' }
    loadClusters()
  } catch (e: any) {
    alert(e.response?.data?.detail || '添加失败')
  } finally {
    loading.value = false
  }
}

async function testConnection(c: Cluster) {
  try {
    await clusterApi.test(c.id)
    alert('连接成功')
  } catch (e: any) {
    alert('连接失败: ' + (e.response?.data?.detail || e.message))
  }
}

function confirmDelete(c: Cluster) {
  if (confirm(`确定删除集群「${c.display_name || c.name}」？`)) {
    clusterApi.delete(c.id).then(() => loadClusters()).catch((e) => alert('删除失败'))
  }
}

onMounted(loadClusters)
</script>

<style scoped>
.action-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.action-buttons .btn {
  min-width: 5.5rem;
  justify-content: center;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.link {
  color: var(--accent);
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
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
}
.modal h2 {
  margin-bottom: 1rem;
  font-size: 1.25rem;
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
