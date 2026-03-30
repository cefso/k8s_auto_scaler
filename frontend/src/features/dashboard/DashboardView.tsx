import { useQuery } from '@tanstack/react-query'
import { resourceApi, analysisApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatBytes } from '@/lib/utils'

interface DashboardViewProps {
  clusterId: number
}

export function DashboardView({ clusterId }: DashboardViewProps) {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['overview', clusterId],
    queryFn: () => resourceApi.metricsOverview(clusterId).then(res => res.data),
  })

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ['events', clusterId],
    queryFn: () => resourceApi.events(clusterId).then(res => res.data.items || []),
  })

  const { data: topPods, isLoading: topPodsLoading } = useQuery({
    queryKey: ['top-pods', clusterId],
    queryFn: () => analysisApi.getTopPods(clusterId, 5, 'cpu').then(res => res.data),
  })

  if (overviewLoading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
  }

  const podStats = overview?.pod_stats || {}

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard label="集群节点" value={overview?.node_count ?? '-'} />
        <StatCard label="命名空间" value={overview?.namespace_count ?? '-'} />
        <StatCard label="Pod 总数" value={podStats.total ?? '-'} />
        <StatCard label="Pod 运行中" value={podStats.running ?? '-'} accent="success" />
        <StatCard label="Pod 等待中" value={podStats.pending ?? '-'} accent="warning" />
        <StatCard label="Pod 异常" value={podStats.failed ?? '-'} accent="error" />
        <StatCard label="Pod 已完成" value={podStats.succeeded ?? '-'} />
        <StatCard label="Deployment" value={overview?.deployment_count ?? '-'} />
        <StatCard label="StatefulSet" value={overview?.statefulset_count ?? '-'} />
        <StatCard label="Ingress" value={overview?.ingress_count ?? '-'} />
        <StatCard label="ApisixRoute" value={overview?.apisixroute_count ?? '-'} />
        <StatCard label="ApisixTls" value={overview?.apisixtls_count ?? '-'} />
        <StatCard label="IngressRoute" value={overview?.ingressroute_count ?? '-'} />
      </div>

      {/* Top Pods */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">CPU 消耗 Top 5 Pods</CardTitle>
          </CardHeader>
          <CardContent>
            {topPodsLoading ? (
              <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin" /></div>
            ) : topPods?.cpu_top?.length ? (
              <div className="space-y-2">
                {topPods.cpu_top.map((pod: any, i: number) => (
                  <div key={`${pod.namespace}-${pod.name}`} className="flex items-center gap-3 text-sm">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? 'bg-yellow-500 text-black' : i === 1 ? 'bg-gray-400 text-black' : i === 2 ? 'bg-amber-700 text-white' : 'bg-muted'
                    }`}>{i + 1}</span>
                    <span className="flex-1 font-mono truncate">{pod.namespace}/{pod.name}</span>
                    <span className="text-muted-foreground">{pod.cpu_usage != null ? `${pod.cpu_usage} Cores` : '-'}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">暂无数据</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">内存消耗 Top 5 Pods</CardTitle>
          </CardHeader>
          <CardContent>
            {topPodsLoading ? (
              <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin" /></div>
            ) : topPods?.memory_top?.length ? (
              <div className="space-y-2">
                {topPods.memory_top.map((pod: any, i: number) => (
                  <div key={`${pod.namespace}-${pod.name}`} className="flex items-center gap-3 text-sm">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? 'bg-yellow-500 text-black' : i === 1 ? 'bg-gray-400 text-black' : i === 2 ? 'bg-amber-700 text-white' : 'bg-muted'
                    }`}>{i + 1}</span>
                    <span className="flex-1 font-mono truncate">{pod.namespace}/{pod.name}</span>
                    <span className="text-muted-foreground">{pod.memory_usage != null ? formatBytes(pod.memory_usage) : '-'}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">暂无数据</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Events */}
      <Card>
        <CardHeader>
          <CardTitle>集群事件</CardTitle>
        </CardHeader>
        <CardContent>
          {eventsLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : events.length === 0 ? (
            <div className="text-sm text-muted-foreground">暂无事件数据</div>
          ) : (
            <div className="space-y-2">
              {events.slice(0, 10).map((event: any, i: number) => (
                <div key={i} className="flex items-start gap-3 text-sm py-2 border-b last:border-0">
                  <Badge variant={event.type === 'Warning' ? 'destructive' : 'secondary'}>
                    {event.type}
                  </Badge>
                  <span className="font-medium min-w-20">{event.reason || '-'}</span>
                  <span className="text-muted-foreground flex-1 truncate">{event.message || '-'}</span>
                  <span className="text-muted-foreground text-xs whitespace-nowrap">{event.age || '-'}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  accent?: 'success' | 'warning' | 'error'
}

function StatCard({ label, value, accent }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4 text-center">
        <div className="text-sm text-muted-foreground mb-1">{label}</div>
        <div className={`text-2xl font-bold font-mono ${
          accent === 'success' ? 'text-success' :
          accent === 'warning' ? 'text-warning' :
          accent === 'error' ? 'text-error' : ''
        }`}>
          {value}
        </div>
      </CardContent>
    </Card>
  )
}

export default DashboardView
