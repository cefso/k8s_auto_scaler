import { useState } from 'react'
import { Outlet, NavLink, useParams, useLocation, useNavigate } from 'react-router-dom'
import { useThemeStore } from '@/stores/themeStore'
import { useQuery } from '@tanstack/react-query'
import { clusterApi, searchApi } from '@/api'
import { cn } from '@/lib/utils'
import { MoonIcon, SunIcon, ServerIcon, ChevronRightIcon, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'

const topNavItems = [
  { path: '/', label: '集群' },
  { path: '/schedules', label: '定时扩缩容' },
  { path: '/audit', label: '审计日志' },
]

// 侧边栏分类
const sidebarSections = [
  {
    key: 'overview',
    label: '概览',
    items: [
      { key: 'dashboard', label: '集群概览' },
      { key: 'nodes', label: '节点概览' },
    ],
  },
  {
    key: 'workload',
    label: '工作负载',
    items: [
      { key: 'deployments', label: 'Deployment' },
      { key: 'statefulsets', label: 'StatefulSet' },
      { key: 'rollouts', label: 'Rollout' },
      { key: 'pods', label: 'Pod' },
      { key: 'hpas', label: 'HPA' },
    ],
  },
  {
    key: 'network',
    label: '网络资源',
    items: [
      { key: 'services', label: 'Service' },
      { key: 'ingresses', label: 'Ingress' },
    ],
  },
  {
    key: 'apisix',
    label: 'Apisix',
    items: [
      { key: 'apisixroutes', label: 'ApisixRoute' },
      { key: 'apisixtlses', label: 'ApisixTls' },
    ],
  },
  {
    key: 'traefik',
    label: 'Traefik',
    items: [
      { key: 'ingressroutes', label: 'IngressRoute' },
      { key: 'ingressroutetcps', label: 'IngressRouteTCP' },
      { key: 'ingressrouteudps', label: 'IngressRouteUDP' },
    ],
  },
  {
    key: 'config',
    label: '配置与密钥',
    items: [
      { key: 'configmaps', label: 'ConfigMap' },
      { key: 'secrets', label: 'Secret' },
    ],
  },
  {
    key: 'app',
    label: 'Helm 应用',
    items: [
      { key: 'helm', label: 'Helm' },
    ],
  },
]

export function AppLayout() {
  const { theme, toggleTheme } = useThemeStore()
  const location = useLocation()
  const navigate = useNavigate()
  const { id: clusterId } = useParams()

  // 判断是否在集群详情页
  const isClusterPage = location.pathname.startsWith('/cluster/') && location.pathname !== '/cluster/'

  // 搜索相关
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchLoading, setSearchLoading] = useState(false)

  // 获取当前 tab
  const searchParams = new URLSearchParams(location.search)
  const currentTab = searchParams.get('tab') || 'dashboard'

  // 搜索功能
  const handleSearch = async () => {
    if (!searchKeyword.trim() || !clusterId) return

    setSearchLoading(true)
    try {
      const res = await searchApi.globalSearch(Number(clusterId), searchKeyword)
      setSearchResults(res.data.items || [])
    } catch (e) {
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }

  const goToResource = (item: any) => {
    const typeMap: Record<string, string> = {
      Pod: 'pods',
      Deployment: 'deployments',
      StatefulSet: 'statefulsets',
      Service: 'services',
      Ingress: 'ingresses',
      ConfigMap: 'configmaps',
      Secret: 'secrets',
      ApisixRoute: 'apisixroutes',
      ApisixTls: 'apisixtlses',
      IngressRoute: 'ingressroutes',
      IngressRouteTCP: 'ingressroutetcps',
      IngressRouteUDP: 'ingressrouteudps',
      HPA: 'hpas',
    }
    const tab = typeMap[item.type]
    if (tab && clusterId) {
      navigate(`/cluster/${clusterId}?tab=${tab}`)
      setSearchResults([])
      setSearchKeyword('')
    }
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      {/* Top Navigation Bar */}
      <header className="h-14 border-b bg-card flex items-center px-4 gap-4">
        <div className="flex items-center gap-2 mr-6">
          <ServerIcon className="h-5 w-5 text-primary" />
          <span className="font-semibold">K8s Auto Scaler</span>
        </div>

        {topNavItems.map((item) => {
          const isActive = item.path === '/'
            ? location.pathname === '/' || location.pathname.startsWith('/cluster/')
            : location.pathname === item.path

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {item.label}
            </NavLink>
          )
        })}

        {/* 全局搜索 - 只在集群页面显示 */}
        {isClusterPage && clusterId && (
          <div className="relative ml-auto flex items-center gap-2">
            <div className="relative">
              <Input
                type="text"
                placeholder="搜索资源..."
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-48 h-8"
              />
              {searchLoading && <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin" />}
            </div>
            {searchResults.length > 0 && (
              <div className="absolute top-full right-0 mt-1 w-64 bg-card border rounded-md shadow-lg z-50 max-h-64 overflow-auto">
                {searchResults.map((item, index) => (
                  <div
                    key={`${item.type}-${item.name}-${index}`}
                    className="px-3 py-2 hover:bg-muted cursor-pointer text-sm"
                    onClick={() => goToResource(item)}
                  >
                    <span className="text-xs text-muted-foreground mr-2">{item.type}</span>
                    <span className="font-mono">{item.namespace}/{item.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - only show on cluster pages */}
        {isClusterPage && clusterId && (
          <aside className="w-56 border-r bg-card flex flex-col overflow-hidden">
            <SidebarContent clusterId={clusterId} currentTab={currentTab} />
          </aside>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>

      {/* Theme Toggle */}
      <button
        onClick={toggleTheme}
        className="fixed bottom-6 right-6 w-11 h-11 rounded-full border bg-card flex items-center justify-center hover:bg-muted transition-colors z-50"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? (
          <SunIcon className="h-5 w-5" />
        ) : (
          <MoonIcon className="h-5 w-5" />
        )}
      </button>
    </div>
  )
}

interface SidebarContentProps {
  clusterId: string
  currentTab: string
}

function SidebarContent({ clusterId, currentTab }: SidebarContentProps) {
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => clusterApi.list().then(res => res.data),
  })

  const activeClusters = clusters.filter((c: any) => c.is_active)

  // 折叠状态
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['overview'])
  )

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Cluster Selector */}
      <div className="p-3 border-b">
        <label className="text-xs text-muted-foreground uppercase tracking-wider">已连接集群</label>
        <select
          value={clusterId}
          onChange={(e) => {
            if (e.target.value) {
              window.location.href = `/cluster/${e.target.value}?tab=dashboard`
            }
          }}
          className="w-full mt-1 px-2 py-1.5 rounded border bg-background text-sm"
        >
          <option value="">选择集群</option>
          {activeClusters.map((c: any) => (
            <option key={c.id} value={c.id}>
              {c.display_name || c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Navigation Sections */}
      <nav className="flex-1 overflow-y-auto p-2">
        {sidebarSections.map((section) => {
          const isExpanded = expandedSections.has(section.key)
          const hasActiveItem = section.items.some(item => item.key === currentTab)

          return (
            <div key={section.key} className="mb-1">
              <button
                onClick={() => toggleSection(section.key)}
                className="w-full flex items-center gap-1 px-2 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                <ChevronRightIcon
                  className={cn(
                    'h-3 w-3 transition-transform',
                    isExpanded && 'rotate-90'
                  )}
                />
                <span className={cn(hasActiveItem && 'text-foreground')}>{section.label}</span>
              </button>

              {isExpanded && (
                <div className="ml-2 mt-0.5 space-y-0.5">
                  {section.items.map((item) => {
                    const isActive = currentTab === item.key
                    return (
                      <NavLink
                        key={item.key}
                        to={`/cluster/${clusterId}?tab=${item.key}`}
                        className={cn(
                          'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors',
                          isActive
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                        )}
                      >
                        <span className="text-xs opacity-50">▪</span>
                        {item.label}
                      </NavLink>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </div>
  )
}
