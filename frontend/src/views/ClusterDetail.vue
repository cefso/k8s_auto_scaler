<template>
  <div>
    <div v-if="loading" class="empty-state">加载中...</div>
    <div v-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>

    <template v-else-if="cluster">
      <div class="page-header">
        <h1 class="page-title">{{ cluster.display_name || cluster.name }}</h1>
        <select
          v-if="hasNamespaceFilter"
          v-model="filterNs"
          class="form-control ns-filter"
          @change="loadResource"
        >
          <option value="">全部命名空间</option>
          <option v-for="ns in namespaces" :key="ns.name" :value="ns.name">{{ ns.name }}</option>
        </select>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">{{ tabLabel }}</span>
        </div>
        <div class="card-body">
          <div v-if="resourceLoading" class="empty-state">加载中...</div>
          <div v-else-if="!items.length" class="empty-state">暂无数据</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="h in tableHeaders" :key="h">{{ h }}</th>
                  <th v-if="hasOperations">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.name + (item.namespace || '')">
                  <td v-for="(val, k) in rowData(item)" :key="k">{{ val }}</td>
                  <td v-if="hasOperations">
                    <div class="action-buttons">
                      <button v-if="hasYaml" class="btn btn-sm btn-secondary" @click="openYamlModal(item)">YAML</button>
                      <button
                        v-if="['deployments', 'statefulsets'].includes(activeTab)"
                        class="btn btn-sm btn-primary"
                        @click="openScaleModal(item)"
                      >
                        扩缩容
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- YAML 查看弹窗 -->
      <div v-if="yamlModal" class="modal-overlay" @click.self="yamlModal = null">
        <div class="modal modal-yaml">
          <div class="modal-header">
            <h2>YAML - {{ yamlModal.namespace }}/{{ yamlModal.name }}</h2>
            <button class="btn btn-sm btn-secondary" @click="yamlModal = null">关闭</button>
          </div>
          <pre v-if="yamlLoading" class="yaml-content">加载中...</pre>
          <pre v-else class="yaml-content">{{ yamlContent }}</pre>
        </div>
      </div>

      <!-- 扩缩容弹窗 -->
      <div v-if="scaleTarget" class="modal-overlay" @click.self="scaleTarget = null">
        <div class="modal">
          <h2>扩缩容</h2>
          <p class="scale-target">
            {{ scaleTarget.resource_type }}: {{ scaleTarget.namespace }}/{{ scaleTarget.name }}
          </p>
          <div class="form-group">
            <label>目标副本数</label>
            <input v-model.number="scaleReplicas" type="number" min="0" class="form-control" />
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" @click="scaleTarget = null">取消</button>
            <button class="btn btn-primary" @click="doScale" :disabled="scaleLoading">确认</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { clusterApi, resourceApi } from '@/api'
import type { Cluster } from '@/api'

const route = useRoute()
const clusterId = computed(() => Number(route.params.id))
const cluster = ref<Cluster | null>(null)
const loading = ref(true)
const error = ref('')
const connectionOk = ref(false)

const tabs = [
  { key: 'helm', label: 'Helm' },
  { key: 'deployments', label: 'Deployment' },
  { key: 'statefulsets', label: 'StatefulSet' },
  { key: 'rollouts', label: 'Rollout' },
  { key: 'pods', label: 'Pod' },
  { key: 'services', label: 'Service' },
  { key: 'ingresses', label: 'Ingress' },
  { key: 'apisixroutes', label: 'ApisixRoute' },
  { key: 'apisixtlses', label: 'ApisixTls' },
  { key: 'configmaps', label: 'ConfigMap' },
  { key: 'secrets', label: 'Secret' },
]

const activeTab = computed(() => {
  const t = route.query.tab as string
  return tabs.some((x) => x.key === t) ? t : 'deployments'
})

const hasNamespaceFilter = computed(() =>
  ['helm', 'deployments', 'statefulsets', 'rollouts', 'pods', 'services', 'ingresses', 'apisixroutes', 'apisixtlses', 'configmaps', 'secrets'].includes(activeTab.value)
)

const hasYaml = computed(() => activeTab.value !== 'helm')
const hasOperations = computed(() => hasYaml.value || ['deployments', 'statefulsets'].includes(activeTab.value))

const namespaces = ref<{ name: string }[]>([])
const items = ref<any[]>([])
const resourceLoading = ref(false)
const filterNs = ref('')

const scaleTarget = ref<any>(null)
const scaleReplicas = ref(0)
const scaleLoading = ref(false)

const yamlModal = ref<{ namespace: string; name: string } | null>(null)
const yamlContent = ref('')
const yamlLoading = ref(false)

const tabLabel = computed(() => tabs.find((t) => t.key === activeTab.value)?.label || '')

const tableHeaders = computed(() => {
  const map: Record<string, string[]> = {
    helm: ['名称', '命名空间', 'Revision', '状态', '年龄'],
    deployments: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    statefulsets: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    rollouts: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    pods: ['名称', '命名空间', '状态', '就绪', '重启', '年龄', '节点'],
    services: ['名称', '命名空间', '类型', 'Cluster IP', '端口', '年龄'],
    ingresses: ['名称', '命名空间', 'Hosts', 'Class', '年龄'],
    apisixroutes: ['名称', '命名空间', 'Hosts', '年龄'],
    apisixtlses: ['名称', '命名空间', 'Hosts', 'Secret', '年龄'],
    configmaps: ['名称', '命名空间', 'Data Keys', '年龄'],
    secrets: ['名称', '命名空间', '类型', 'Data Keys', '年龄'],
  }
  return map[activeTab.value] || []
})

function rowData(item: any) {
  switch (activeTab.value) {
    case 'helm':
      return {
        名称: item.name,
        命名空间: item.namespace,
        Revision: item.revision,
        状态: item.status || 'deployed',
        年龄: item.age,
      }
    case 'deployments':
    case 'statefulsets':
    case 'rollouts':
      return {
        名称: item.name,
        命名空间: item.namespace,
        副本: item.replicas,
        就绪: item.ready_replicas,
        状态: item.status,
        年龄: item.age,
      }
    case 'pods':
      return {
        名称: item.name,
        命名空间: item.namespace,
        状态: item.status,
        就绪: item.ready,
        重启: item.restarts,
        年龄: item.age,
        节点: item.node || '-',
      }
    case 'services':
      return {
        名称: item.name,
        命名空间: item.namespace,
        类型: item.type || 'ClusterIP',
        'Cluster IP': item.cluster_ip || '-',
        端口: Array.isArray(item.ports) ? item.ports.join(', ') : (item.ports || '-'),
        年龄: item.age,
      }
    case 'ingresses':
      return {
        名称: item.name,
        命名空间: item.namespace,
        Hosts: item.hosts || '-',
        Class: item.class_name || '-',
        年龄: item.age,
      }
    case 'apisixroutes':
      return {
        名称: item.name,
        命名空间: item.namespace,
        Hosts: item.hosts || '-',
        年龄: item.age,
      }
    case 'apisixtlses':
      return {
        名称: item.name,
        命名空间: item.namespace,
        Hosts: item.hosts || '-',
        Secret: item.secret || '-',
        年龄: item.age,
      }
    case 'configmaps':
      return {
        名称: item.name,
        命名空间: item.namespace,
        'Data Keys': (item.data_keys || []).join(', ') || '-',
        年龄: item.age,
      }
    case 'secrets':
      return {
        名称: item.name,
        命名空间: item.namespace,
        类型: item.type || 'Opaque',
        'Data Keys': (item.data_keys || []).join(', ') || '-',
        年龄: item.age,
      }
    default:
      return item
  }
}

async function loadCluster() {
  loading.value = true
  error.value = ''
  connectionOk.value = false
  cluster.value = null
  items.value = []
  namespaces.value = []
  try {
    const res = await clusterApi.get(clusterId.value)
    cluster.value = res.data
    try {
      await clusterApi.test(clusterId.value)
    } catch (e: any) {
      const msg = String(e.response?.data?.detail || e.message || '未知错误')
      error.value = msg.includes('连接') ? msg : `集群连接失败: ${msg}`
      loading.value = false
      return
    }
    connectionOk.value = true
    await loadResource()
  } catch (e: any) {
    error.value = String(e.response?.data?.detail || e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadNamespaces() {
  const res = await resourceApi.namespaces(clusterId.value)
  namespaces.value = res.data.items
}

async function loadResource() {
  resourceLoading.value = true
  try {
    let res: any
    if (activeTab.value === 'deployments') {
      res = await resourceApi.deployments(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'statefulsets') {
      res = await resourceApi.statefulsets(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'rollouts') {
      res = await resourceApi.rollouts(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'helm') {
      res = await resourceApi.helm(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'pods') {
      res = await resourceApi.pods(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'services') {
      res = await resourceApi.services(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'ingresses') {
      res = await resourceApi.ingresses(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'apisixroutes') {
      res = await resourceApi.apisixroutes(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'apisixtlses') {
      res = await resourceApi.apisixtlses(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'configmaps') {
      res = await resourceApi.configmaps(clusterId.value, filterNs.value || undefined)
    } else {
      res = await resourceApi.secrets(clusterId.value, filterNs.value || undefined)
    }
    items.value = res.data.items
    loadNamespaces()
  } catch (e: any) {
    items.value = []
  } finally {
    resourceLoading.value = false
  }
}

async function openYamlModal(item: any) {
  yamlModal.value = { namespace: item.namespace, name: item.name }
  yamlContent.value = ''
  yamlLoading.value = true
  try {
    const res = await resourceApi.getYaml(
      clusterId.value,
      activeTab.value,
      item.namespace,
      item.name
    )
    yamlContent.value = res.data.yaml
  } catch (e: any) {
    yamlContent.value = '加载失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    yamlLoading.value = false
  }
}

function openScaleModal(item: any) {
  scaleTarget.value = {
    resource_type: activeTab.value === 'deployments' ? 'Deployment' : 'StatefulSet',
    namespace: item.namespace,
    name: item.name,
  }
  scaleReplicas.value = item.replicas ?? 0
}

async function doScale() {
  if (!scaleTarget.value) return
  scaleLoading.value = true
  try {
    const { scalingApi } = await import('@/api')
    await scalingApi.scale(clusterId.value, {
      namespace: scaleTarget.value.namespace,
      resource_type: scaleTarget.value.resource_type,
      resource_name: scaleTarget.value.name,
      replicas: scaleReplicas.value,
    })
    scaleTarget.value = null
    loadResource()
  } catch (e: any) {
    alert(e.response?.data?.detail || '扩缩容失败')
  } finally {
    scaleLoading.value = false
  }
}

watch(activeTab, () => {
  filterNs.value = ''
  if (connectionOk.value) loadResource()
}, { immediate: true })

watch(clusterId, loadCluster)

onMounted(loadCluster)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.card-title {
  font-weight: 500;
  font-size: 0.95rem;
}
.ns-filter {
  width: auto;
  min-width: 180px;
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
.modal h2 {
  margin-bottom: 1rem;
  font-size: 1.25rem;
}
.scale-target {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}
.action-buttons {
  display: flex;
  gap: 0.35rem;
}
.modal-yaml {
  max-width: 90vw;
  width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.modal-header h2 {
  margin: 0;
  font-size: 1rem;
  font-family: var(--font-mono);
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
</style>
