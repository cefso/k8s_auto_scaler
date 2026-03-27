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
          <h3 class="sidebar-title collapsible" @click="toggleSection('overview')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'overview' }">▸</span>
            概览
          </h3>
          <nav v-show="expandedSection === 'overview'" class="sidebar-nav">
            <router-link
              :to="`/cluster/${currentClusterId}?tab=dashboard`"
              :class="['sidebar-item', { active: currentTab === 'dashboard' }]"
            >
              <span class="sidebar-icon">▪</span>
              概览
            </router-link>
            <router-link
              :to="`/cluster/${currentClusterId}?tab=nodes`"
              :class="['sidebar-item', { active: currentTab === 'nodes' }]"
            >
              <span class="sidebar-icon">▪</span>
              节点
            </router-link>
          </nav>
        </section>
        <section v-if="currentClusterId && onClusterPage" class="sidebar-section">
          <h3 class="sidebar-title collapsible" @click="toggleSection('workload')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'workload' }">▸</span>
            工作负载
          </h3>
          <nav v-show="expandedSection === 'workload'" class="sidebar-nav">
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
          <h3 class="sidebar-title collapsible" @click="toggleSection('network')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'network' }">▸</span>
            网络资源
          </h3>
          <nav v-show="expandedSection === 'network'" class="sidebar-nav">
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
          <h3 class="sidebar-title collapsible" @click="toggleSection('apisix')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'apisix' }">▸</span>
            Apisix
          </h3>
          <nav v-show="expandedSection === 'apisix'" class="sidebar-nav">
            <router-link
              v-for="r in apisixTypes"
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
          <h3 class="sidebar-title collapsible" @click="toggleSection('traefik')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'traefik' }">▸</span>
            Traefik
          </h3>
          <nav v-show="expandedSection === 'traefik'" class="sidebar-nav">
            <router-link
              v-for="r in traefikTypes"
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
          <h3 class="sidebar-title collapsible" @click="toggleSection('config')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'config' }">▸</span>
            配置与密钥
          </h3>
          <nav v-show="expandedSection === 'config'" class="sidebar-nav">
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
          <h3 class="sidebar-title collapsible" @click="toggleSection('app')">
            <span class="collapse-arrow" :class="{ collapsed: expandedSection !== 'app' }">▸</span>
            Helm 应用
          </h3>
          <nav v-show="expandedSection === 'app'" class="sidebar-nav">
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
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClusterStore } from '@/stores/cluster'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()
const router = useRouter()
const clusterStore = useClusterStore()

// 侧边栏折叠状态（展开的栏目 key）
const expandedSection = ref<string | null>('overview')

function toggleSection(key: string) {
  if (expandedSection.value === key) {
    expandedSection.value = null
  } else {
    expandedSection.value = key
  }
}

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
]

const apisixTypes = [
  { key: 'apisixroutes', label: 'ApisixRoute' },
  { key: 'apisixtlses', label: 'ApisixTls' },
]

const traefikTypes = [
  { key: 'ingressroutes', label: 'IngressRoute' },
  { key: 'ingressroutetcps', label: 'IngressRouteTCP' },
  { key: 'ingressrouteudps', label: 'IngressRouteUDP' },
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
    router.push(`/cluster/${id}?tab=dashboard`)
  }
}

const currentClusterId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

const onClusterPage = computed(() => route.path.startsWith('/cluster/'))

const onSchedulePage = computed(() => route.path === '/schedules')

const currentTab = computed(() => route.query.tab as string || 'dashboard')

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

<style scoped>
.sidebar-title.collapsible {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.sidebar-title.collapsible:hover {
  opacity: 0.8;
}
.collapse-arrow {
  font-size: 0.75rem;
  transition: transform 0.15s ease;
  display: inline-block;
}
.collapse-arrow.collapsed {
  transform: rotate(0deg);
}
.collapse-arrow:not(.collapsed) {
  transform: rotate(90deg);
}
</style>
