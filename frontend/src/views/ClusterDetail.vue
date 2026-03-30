<template>
  <div>
    <div v-if="loading" class="empty-state">加载中...</div>
    <div v-if="error" class="empty-state" style="color: var(--error)">{{ error }}</div>

    <template v-else-if="cluster">
      <div class="page-header">
        <h1 class="page-title">{{ cluster.display_name || cluster.name }}</h1>
        <div class="page-header-actions">
          <select
            v-if="hasNamespaceFilter"
            v-model="filterNs"
            class="form-control ns-filter"
            @change="loadResource"
          >
            <option value="">全部命名空间</option>
            <option v-for="ns in namespaces" :key="ns.name" :value="ns.name">{{ ns.name }}</option>
          </select>
          <button class="btn btn-secondary" @click="refreshAll">刷新</button>
        </div>
      </div>

      <!-- Dashboard 概览 -->
      <Dashboard v-if="activeTab === 'dashboard'" :cluster-id="clusterId" />
      <NodeMetrics v-if="activeTab === 'nodes'" :cluster-id="clusterId" />

      <div v-if="activeTab !== 'nodes' && activeTab !== 'dashboard'" class="card">
        <div class="card-header">
          <span class="card-title">{{ tabLabel }}</span>
          <!-- 批量操作栏 (Pod 列表时显示) -->
          <div v-if="activeTab === 'pods' && selectedItems.length > 0" class="batch-actions">
            <span class="batch-count">已选择 {{ selectedItems.length }} 项</span>
            <button class="btn btn-sm btn-secondary" @click="batchRestart">批量重启</button>
            <button class="btn btn-sm btn-danger" @click="batchDelete">批量删除</button>
            <button class="btn btn-sm btn-secondary" @click="openLabelModal">批量修改标签</button>
            <button class="btn btn-sm btn-secondary" @click="clearSelection">取消选择</button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="resourceLoading" class="empty-state">加载中...</div>
          <div v-else-if="helmError" class="empty-state" style="color: var(--warning)">{{ helmError }}</div>
          <div v-else-if="!items.length" class="empty-state">暂无数据</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-if="activeTab === 'pods'" class="checkbox-col">
                    <input
                      type="checkbox"
                      :checked="isAllSelected"
                      :indeterminate.prop="isSomeSelected && !isAllSelected"
                      @change="toggleSelectAll"
                    />
                  </th>
                  <th v-for="h in tableHeaders" :key="h">{{ h }}</th>
                  <th v-if="hasOperations">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.name + (item.namespace || '')">
                  <td v-if="activeTab === 'pods'" class="checkbox-col">
                    <input
                      type="checkbox"
                      :checked="isItemSelected(item)"
                      @change="toggleSelectItem(item)"
                    />
                  </td>
                  <td v-for="(val, k) in rowData(item)" :key="k">{{ val }}</td>
                  <td v-if="hasOperations">
                    <div class="action-buttons">
                      <button v-if="isWorkloadTab" class="btn btn-sm btn-secondary" @click="openWorkloadDetail(item)">详情</button>
                      <button v-if="activeTab === 'helm'" class="btn btn-sm btn-secondary" @click="openHelmValuesModal(item)">获取 Values</button>
                      <button v-if="hasYaml && activeTab !== 'helm'" class="btn btn-sm btn-secondary" @click="openYamlModal(item)">YAML</button>
                      <button
                        v-if="['deployments', 'statefulsets'].includes(activeTab)"
                        class="btn btn-sm btn-primary"
                        @click="openScaleModal(item)"
                      >
                        扩缩容
                      </button>
                      <button v-if="activeTab === 'pods'" class="btn btn-sm btn-secondary" @click="openLogViewer(item)">日志</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- YAML 查看弹窗 -->
      <div v-if="yamlModal" class="modal-overlay" @click.self="closeYamlModal">
        <div class="modal modal-yaml">
          <div class="modal-header">
            <h2>YAML - {{ yamlModal.namespace }}/{{ yamlModal.name }}</h2>
            <div class="modal-header-actions">
              <button v-if="hasCollapsedFields" class="btn btn-sm btn-secondary" @click="toggleYamlFields">
                {{ showCollapsedFields ? '折叠冗余字段' : '显示全部字段' }}
              </button>
              <button class="btn btn-sm btn-secondary" @click="closeYamlModal">关闭</button>
            </div>
          </div>
          <pre v-if="yamlLoading" class="yaml-content">加载中...</pre>
          <pre v-else class="yaml-content">{{ displayYaml }}</pre>
        </div>
      </div>

      <!-- Helm Values 弹窗 -->
      <div v-if="helmValuesModal" class="modal-overlay" @click.self="closeHelmValuesModal">
        <div class="modal modal-yaml">
          <div class="modal-header">
            <h2>Values - {{ helmValuesModal.namespace }}/{{ helmValuesModal.name }}</h2>
            <div class="modal-header-actions">
              <button class="btn btn-sm btn-secondary" @click="closeHelmValuesModal">关闭</button>
            </div>
          </div>
          <pre v-if="helmValuesLoading" class="yaml-content">加载中...</pre>
          <pre v-else class="yaml-content">{{ helmValuesContent }}</pre>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clusterApi, resourceApi } from '@/api'
import type { Cluster } from '@/api'
import Dashboard from './Dashboard.vue'
import NodeMetrics from './NodeMetrics.vue'
import LogViewer from '@/components/LogViewer.vue'

const route = useRoute()
const router = useRouter()
const clusterId = computed(() => Number(route.params.id))
const cluster = ref<Cluster | null>(null)
const loading = ref(true)
const error = ref('')
const connectionOk = ref(false)

const tabs = [
  { key: 'dashboard', label: '集群概览' },
  { key: 'nodes', label: '节点概览' },
  { key: 'helm', label: 'Helm' },
  { key: 'hpas', label: 'HPA' },
  { key: 'deployments', label: 'Deployment' },
  { key: 'statefulsets', label: 'StatefulSet' },
  { key: 'rollouts', label: 'Rollout' },
  { key: 'pods', label: 'Pod' },
  { key: 'services', label: 'Service' },
  { key: 'ingresses', label: 'Ingress' },
  { key: 'ingressroutes', label: 'IngressRoute' },
  { key: 'ingressroutetcps', label: 'IngressRouteTCP' },
  { key: 'ingressrouteudps', label: 'IngressRouteUDP' },
  { key: 'apisixroutes', label: 'ApisixRoute' },
  { key: 'apisixtlses', label: 'ApisixTls' },
  { key: 'configmaps', label: 'ConfigMap' },
  { key: 'secrets', label: 'Secret' },
]

const activeTab = computed(() => {
  const t = route.query.tab as string
  return tabs.some((x) => x.key === t) ? t : 'dashboard'
})

const hasNamespaceFilter = computed(() =>
  ['deployments', 'statefulsets', 'rollouts', 'pods', 'services', 'ingresses', 'ingressroutes', 'ingressroutetcps', 'ingressrouteudps', 'apisixroutes', 'apisixtlses', 'configmaps', 'secrets', 'hpas'].includes(activeTab.value)
)

const hasYaml = computed(() => activeTab.value !== 'helm')
const hasOperations = computed(() => hasYaml.value || ['deployments', 'statefulsets', 'helm'].includes(activeTab.value))
const isWorkloadTab = computed(() => ['deployments', 'statefulsets', 'rollouts'].includes(activeTab.value))

// 批量选择相关
const selectedItems = ref<any[]>([])

const isAllSelected = computed(() => {
  return items.value.length > 0 && items.value.every((item) => isItemSelected(item))
})

const isSomeSelected = computed(() => {
  return items.value.some((item) => isItemSelected(item))
})

function isItemSelected(item: any): boolean {
  return selectedItems.value.some(
    (s) => s.namespace === item.namespace && s.name === item.name
  )
}

function toggleSelectItem(item: any) {
  const index = selectedItems.value.findIndex(
    (s) => s.namespace === item.namespace && s.name === item.name
  )
  if (index >= 0) {
    selectedItems.value.splice(index, 1)
  } else {
    selectedItems.value.push({ namespace: item.namespace, name: item.name })
  }
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedItems.value = []
  } else {
    selectedItems.value = items.value.map((item) => ({
      namespace: item.namespace,
      name: item.name,
    }))
  }
}

function clearSelection() {
  selectedItems.value = []
}

async function batchRestart() {
  if (!selectedItems.value.length) return
  if (!confirm(`确定要重启选中的 ${selectedItems.value.length} 个 Pod 吗？`)) return
  try {
    const { batchApi } = await import('@/api')
    const res = await batchApi.restartPods(clusterId.value, selectedItems.value)
    alert(
      `批量重启完成: 成功 ${res.data.success.length}, 失败 ${res.data.failed.length}`
    )
    clearSelection()
    loadResource()
  } catch (e: any) {
    alert('批量重启失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function batchDelete() {
  if (!selectedItems.value.length) return
  if (
    !confirm(
      `确定要删除选中的 ${selectedItems.value.length} 个 Pod 吗？此操作不可恢复！`
    )
  )
    return
  try {
    const { batchApi } = await import('@/api')
    const res = await batchApi.deletePods(clusterId.value, selectedItems.value)
    alert(
      `批量删除完成: 成功 ${res.data.success.length}, 失败 ${res.data.failed.length}`
    )
    clearSelection()
    loadResource()
  } catch (e: any) {
    alert('批量删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function openLabelModal() {
  const labels = prompt('请输入要添加/更新的标签，格式: key1=value1,key2=value2')
  if (!labels) return
  try {
    const labelDict: Record<string, string> = {}
    labels.split(',').forEach((pair) => {
      const [key, value] = pair.trim().split('=')
      if (key && value) {
        labelDict[key.trim()] = value.trim()
      }
    })
    if (Object.keys(labelDict).length === 0) {
      alert('标签格式无效')
      return
    }
    const { batchApi } = await import('@/api')
    const res = await batchApi.updateLabels(
      clusterId.value,
      selectedItems.value,
      labelDict
    )
    alert(
      `批量更新标签完成: 成功 ${res.data.success.length}, 失败 ${res.data.failed.length}`
    )
    clearSelection()
    loadResource()
  } catch (e: any) {
    alert('批量更新标签失败: ' + (e.response?.data?.detail || e.message))
  }
}

function getWorkloadKind(): string {
  const map: Record<string, string> = {
    deployments: 'Deployment',
    statefulsets: 'StatefulSet',
    rollouts: 'Rollout',
  }
  return map[activeTab.value] || ''
}

const namespaces = ref<{ name: string }[]>([])
const items = ref<any[]>([])
const resourceLoading = ref(false)
const filterNs = ref('')

const scaleTarget = ref<any>(null)
const scaleReplicas = ref(0)
const scaleLoading = ref(false)

const yamlModal = ref<{ namespace: string; name: string } | null>(null)
const yamlContent = ref('')
const yamlRawContent = ref('')  // 原始 YAML（未折叠）
const yamlLoading = ref(false)
const showCollapsedFields = ref(false)
const helmError = ref('')
const helmValuesModal = ref<{ namespace: string; name: string } | null>(null)
const helmValuesContent = ref('')
const helmValuesLoading = ref(false)

// 日志相关
const showLogViewer = ref(false)
const logPodName = ref('')
const logPodNamespace = ref('')

const hasCollapsedFields = computed(() => {
  // 检查原始 YAML 中是否包含需要折叠的字段
  const raw = yamlRawContent.value
  if (!raw) return false
  // 使用正则匹配字段名（行首缩进 + 字段名 + : 结尾），使用 m 标志匹配行尾
  const pattern = /^\s*(managedFields|status):\s*$/m
  return pattern.test(raw)
})

const displayYaml = computed(() => {
  if (showCollapsedFields.value) {
    return yamlRawContent.value
  }
  return yamlContent.value
})

function closeYamlModal() {
  yamlModal.value = null
  showCollapsedFields.value = false
}

function toggleYamlFields() {
  showCollapsedFields.value = !showCollapsedFields.value
}

const tabLabel = computed(() => tabs.find((t) => t.key === activeTab.value)?.label || '')

const tableHeaders = computed(() => {
  const map: Record<string, string[]> = {
    helm: ['名称', '命名空间', 'Chart', 'App Version', 'Revision', '状态'],
    hpas: ['名称', '命名空间', '最小副本', '最大副本', '当前副本', 'CPU', '内存', '年龄'],
    deployments: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    statefulsets: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    rollouts: ['名称', '命名空间', '副本', '就绪', '状态', '年龄'],
    pods: ['名称', '命名空间', '状态', '就绪', '重启', '年龄', '节点'],
    services: ['名称', '命名空间', '类型', 'Cluster IP', '端口', '年龄'],
    ingresses: ['名称', '命名空间', 'Hosts', 'Class', 'TLS', '年龄'],
    ingressroutes: ['名称', '命名空间', 'Hosts', 'EntryPoints', '年龄'],
    ingressroutetcps: ['名称', '命名空间', 'EntryPoints', '年龄'],
    ingressrouteudps: ['名称', '命名空间', 'EntryPoints', '年龄'],
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
        Chart: item.chart || '-',
        'App Version': item.app_version || '-',
        Revision: item.revision,
        状态: item.status || 'deployed',
      }
    case 'hpas':
      return {
        名称: item.name,
        命名空间: item.namespace,
        最小副本: item.min_replicas ?? '-',
        最大副本: item.max_replicas ?? '-',
        当前副本: item.current_replicas ?? '-',
        CPU: item.cpu_percent !== null ? `${item.cpu_percent}%` : '-',
        内存: item.memory_percent !== null ? `${item.memory_percent}%` : '-',
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
        TLS: item.tls || '-',
        年龄: item.age,
      }
    case 'ingressroutes':
      return {
        名称: item.name,
        命名空间: item.namespace,
        Hosts: item.hosts || '-',
        EntryPoints: item.entry_points || '-',
        年龄: item.age,
      }
    case 'ingressroutetcps':
      return {
        名称: item.name,
        命名空间: item.namespace,
        EntryPoints: item.entry_points || '-',
        年龄: item.age,
      }
    case 'ingressrouteudps':
      return {
        名称: item.name,
        命名空间: item.namespace,
        EntryPoints: item.entry_points || '-',
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
  // Dashboard tab has its own data loading
  if (activeTab.value === 'dashboard') {
    resourceLoading.value = false
    return
  }
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
      helmError.value = res.data.helm_available === false ? (res.data.error || 'helm 未安装') : ''
    } else if (activeTab.value === 'pods') {
      res = await resourceApi.pods(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'services') {
      res = await resourceApi.services(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'ingresses') {
      res = await resourceApi.ingresses(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'ingressroutes') {
      res = await resourceApi.ingressroutes(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'ingressroutetcps') {
      res = await resourceApi.ingressroutetcps(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'ingressrouteudps') {
      res = await resourceApi.ingressrouteudps(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'apisixroutes') {
      res = await resourceApi.apisixroutes(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'apisixtlses') {
      res = await resourceApi.apisixtlses(clusterId.value, filterNs.value || undefined)
    } else if (activeTab.value === 'hpas') {
      res = await resourceApi.hpas(clusterId.value, filterNs.value || undefined)
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

async function refreshAll() {
  await Promise.all([loadResource(), loadNamespaces()])
}

async function openYamlModal(item: any) {
  yamlModal.value = { namespace: item.namespace, name: item.name }
  yamlContent.value = ''
  yamlRawContent.value = ''
  yamlLoading.value = true
  showCollapsedFields.value = false
  try {
    const res = await resourceApi.getYaml(
      clusterId.value,
      activeTab.value,
      item.namespace,
      item.name
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

function collapseYamlFields(yaml: string): string {
  const lines = yaml.split('\n')
  const result: string[] = []
  const fieldsToCollapse = ['managedFields', 'status']

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 跳过空行，直接传递
    if (line.trim() === '') {
      result.push(line)
      continue
    }

    // 检查是否是需要折叠的字段（行尾是冒号，没有值）
    const fieldMatch = line.match(/^(\s*)(\w+):\s*$/)
    if (fieldMatch) {
      const fieldIndent = fieldMatch[1].length
      const fieldName = fieldMatch[2]

      if (fieldsToCollapse.includes(fieldName)) {
        // 找到目标字段，添加折叠标记
        result.push(`${fieldMatch[1]}# --- ${fieldName} 已折叠 ---`)

        // 跳过该字段的所有子行
        i++
        let contentIndent: number | null = null
        let isArray = false

        while (i < lines.length) {
          const currentLine = lines[i]

          // 空行跳过
          if (currentLine.trim() === '') {
            i++
            continue
          }

          const currentIndent = currentLine.search(/\S/)

          // 记录第一个内容行的缩进
          if (contentIndent === null) {
            contentIndent = currentIndent
            // 检查是否是数组（内容以 `-` 开头）
            isArray = currentLine.trim().startsWith('-')
          }

          if (isArray) {
            // 对于数组：
            // 缩进 <= contentIndent - 1：回到上级，停止
            if (currentIndent <= contentIndent - 1) {
              break
            }
            // 缩进 == contentIndent 且不是数组项：新的兄弟字段，停止
            if (currentIndent === contentIndent && !currentLine.trim().startsWith('-')) {
              break
            }
            // 否则继续（嵌套内容或数组项延续）
          } else {
            // 对于非数组对象：当缩进回到 fieldIndent 级别时停止
            if (currentIndent <= fieldIndent) {
              break
            }
          }

          i++
        }
        continue
      }
    }

    // 普通行，直接保留
    result.push(line)
  }

  return result.join('\n')
}

function openScaleModal(item: any) {
  scaleTarget.value = {
    resource_type: activeTab.value === 'deployments' ? 'Deployment' : 'StatefulSet',
    namespace: item.namespace,
    name: item.name,
  }
  scaleReplicas.value = item.replicas ?? 0
}

function openWorkloadDetail(item: any) {
  router.push(
    `/cluster/${clusterId.value}/workload?kind=${getWorkloadKind()}&namespace=${item.namespace}&name=${item.name}`
  )
}

async function openHelmValuesModal(item: any) {
  helmValuesModal.value = { namespace: item.namespace, name: item.name }
  helmValuesContent.value = ''
  helmValuesLoading.value = true
  try {
    const res = await resourceApi.helmGetValues(clusterId.value, item.namespace, item.name)
    helmValuesContent.value = res.data.values || '# 无 values 内容'
  } catch (e: any) {
    helmValuesContent.value = '加载失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    helmValuesLoading.value = false
  }
}

function closeHelmValuesModal() {
  helmValuesModal.value = null
}

function openLogViewer(pod: any) {
  logPodName.value = pod.name
  logPodNamespace.value = pod.namespace
  showLogViewer.value = true
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
  helmError.value = ''
  clearSelection()
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
.page-header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.card-title {
  font-weight: 500;
  font-size: 0.95rem;
}
.batch-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}
.batch-count {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-right: 0.5rem;
}
.btn-danger {
  background: var(--error);
  color: white;
  border-color: var(--error);
}
.btn-danger:hover {
  background: #d32f2f;
  border-color: #d32f2f;
}
.checkbox-col {
  width: 30px;
  text-align: center;
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
</style>
