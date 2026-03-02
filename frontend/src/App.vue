<template>
  <div class="app">
    <header class="header">
      <router-link to="/" class="logo">
        <span class="logo-icon">⎈</span>
        <span class="logo-text">K8s Auto Scaler</span>
      </router-link>
      <nav class="nav">
        <router-link to="/" class="nav-link">集群管理</router-link>
        <router-link to="/schedules" class="nav-link">定时扩缩容</router-link>
      </nav>
    </header>

    <div class="layout">
      <aside class="sidebar">
        <section v-if="!onSchedulePage" class="sidebar-section">
          <h3 class="sidebar-title">已连接集群</h3>
          <div v-if="clusterStore.loading" class="sidebar-loading">加载中...</div>
          <div v-else-if="!activeClusters.length" class="sidebar-empty">
            暂无集群
            <router-link to="/" class="sidebar-add">+ 添加集群</router-link>
          </div>
          <select
            v-else
            :value="currentClusterId ?? ''"
            class="sidebar-select"
            @change="onClusterChange"
          >
            <option value="">选择集群</option>
            <option
              v-for="c in activeClusters"
              :key="c.id"
              :value="c.id"
            >
              {{ c.display_name || c.name }}
            </option>
          </select>
        </section>

        <section v-if="currentClusterId && onClusterPage" class="sidebar-section">
          <h3 class="sidebar-title">工作负载</h3>
          <nav class="sidebar-nav">
            <router-link
              v-for="r in resourceTypes"
              :key="r.key"
              :to="`/cluster/${currentClusterId}?tab=${r.key}`"
              :class="['sidebar-item', { active: currentTab === r.key }]"
            >
              <span class="sidebar-icon">▪</span>
              {{ r.label }}
            </router-link>
          </nav>
        </section>
        <section v-if="currentClusterId && onClusterPage" class="sidebar-section">
          <h3 class="sidebar-title">网络</h3>
          <nav class="sidebar-nav">
            <router-link
              v-for="r in networkTypes"
              :key="r.key"
              :to="`/cluster/${currentClusterId}?tab=${r.key}`"
              :class="['sidebar-item', { active: currentTab === r.key }]"
            >
              <span class="sidebar-icon">▪</span>
              {{ r.label }}
            </router-link>
          </nav>
        </section>
        <section v-if="currentClusterId && onClusterPage" class="sidebar-section">
          <h3 class="sidebar-title">配置管理</h3>
          <nav class="sidebar-nav">
            <router-link
              v-for="r in configTypes"
              :key="r.key"
              :to="`/cluster/${currentClusterId}?tab=${r.key}`"
              :class="['sidebar-item', { active: currentTab === r.key }]"
            >
              <span class="sidebar-icon">▪</span>
              {{ r.label }}
            </router-link>
          </nav>
        </section>

        <section v-if="currentClusterId && onClusterPage" class="sidebar-section">
          <h3 class="sidebar-title">应用</h3>
          <nav class="sidebar-nav">
            <router-link
              v-for="r in appTypes"
              :key="r.key"
              :to="`/cluster/${currentClusterId}?tab=${r.key}`"
              :class="['sidebar-item', { active: currentTab === r.key }]"
            >
              <span class="sidebar-icon">▪</span>
              {{ r.label }}
            </router-link>
          </nav>
        </section>
      </aside>

      <main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <button
      class="theme-toggle"
      :title="themeStore.theme === 'dark' ? '切换为亮色模式' : '切换为暗色模式'"
      @click="themeStore.toggleTheme"
    >
      {{ themeStore.theme === 'dark' ? '☀' : '🌙' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClusterStore } from '@/stores/cluster'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()
const router = useRouter()
const clusterStore = useClusterStore()

const appTypes = [
  { key: 'helm', label: 'Helm' },
]

const resourceTypes = [
  { key: 'deployments', label: 'Deployment' },
  { key: 'statefulsets', label: 'StatefulSet' },
  { key: 'rollouts', label: 'Rollout' },
  { key: 'pods', label: 'Pod' },
]

const networkTypes = [
  { key: 'services', label: 'Service' },
  { key: 'ingresses', label: 'Ingress' },
  { key: 'apisixroutes', label: 'ApisixRoute' },
  { key: 'apisixtlses', label: 'ApisixTls' },
]

const configTypes = [
  { key: 'configmaps', label: 'ConfigMap' },
  { key: 'secrets', label: 'Secret' },
]

const activeClusters = computed(() =>
  clusterStore.clusters.filter((x) => x.is_active)
)

function onClusterChange(e: Event) {
  const target = e.target as HTMLSelectElement
  const id = target.value ? Number(target.value) : null
  if (id) {
    router.push(`/cluster/${id}?tab=deployments`)
  }
}

const currentClusterId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

const onClusterPage = computed(() => route.path.startsWith('/cluster/'))

const onSchedulePage = computed(() => route.path === '/schedules')

const currentTab = computed(() => route.query.tab as string || 'deployments')

watch(
  () => route.path,
  () => {
    if (route.path.startsWith('/cluster/') || route.path === '/') {
      clusterStore.fetchClusters()
    }
  },
)

onMounted(() => {
  clusterStore.fetchClusters()
  themeStore.initTheme()
})
</script>
