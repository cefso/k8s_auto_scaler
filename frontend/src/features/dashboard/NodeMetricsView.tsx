import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { resourceApi, analysisApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatBytes } from '@/lib/utils'

interface NodeMetricsViewProps {
  clusterId: number
}

export function NodeMetricsView({ clusterId }: NodeMetricsViewProps) {
  const [selectedNode, setSelectedNode] = useState<string>('__all__')

  const { data, isLoading } = useQuery({
    queryKey: ['node-metrics', clusterId],
    queryFn: () => resourceApi.metricsNodes(clusterId).then(res => res.data),
  })

  const { data: topPodsData, isLoading: topPodsLoading } = useQuery({
    queryKey: ['top-pods', clusterId, selectedNode],
    queryFn: async () => {
      const [cpuRes, memRes] = await Promise.all([
        analysisApi.getTopPods(clusterId, 5, 'cpu', selectedNode === '__all__' ? undefined : selectedNode),
        analysisApi.getTopPods(clusterId, 5, 'memory', selectedNode === '__all__' ? undefined : selectedNode),
      ])
      return {
        cpuTop: cpuRes.data.cpu_top || [],
        memoryTop: memRes.data.memory_top || [],
      }
    },
  })

  if (isLoading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
  }

  const nodes = data?.items || []

  // 计算汇总值
  const totalCpu = nodes.reduce((sum: number, n: any) => sum + (n.cpu_request || 0), 0).toFixed(2)
  const usedCpu = nodes.reduce((sum: number, n: any) => sum + (n.cpu_usage || 0), 0).toFixed(2)
  const totalMemory = nodes.reduce((sum: number, n: any) => sum + (n.memory_request || 0), 0)
  const usedMemory = nodes.reduce((sum: number, n: any) => sum + (n.memory_usage || 0), 0)

  const getUsageColor = (usage?: number) => {
    if (usage === undefined || usage === null) return ''
    if (usage >= 90) return 'text-error'
    if (usage >= 70) return 'text-warning'
    return 'text-success'
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-sm text-muted-foreground mb-1">节点数</div>
            <div className="text-2xl font-bold font-mono">{nodes.length || '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-sm text-muted-foreground mb-1">CPU 总量</div>
            <div className="text-2xl font-bold font-mono">{totalCpu} Cores</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-sm text-muted-foreground mb-1">CPU 使用</div>
            <div className="text-2xl font-bold font-mono">{usedCpu} Cores</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-sm text-muted-foreground mb-1">内存总量</div>
            <div className="text-2xl font-bold font-mono">{formatBytes(totalMemory)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-sm text-muted-foreground mb-1">内存使用</div>
            <div className="text-2xl font-bold font-mono">{formatBytes(usedMemory)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Node Details Table */}
      <Card>
        <CardHeader>
          <CardTitle>节点详情</CardTitle>
        </CardHeader>
        <CardContent>
          {nodes.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-8">暂无节点数据</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>节点</TableHead>
                  <TableHead>CPU Request</TableHead>
                  <TableHead>CPU Limit</TableHead>
                  <TableHead>CPU Usage</TableHead>
                  <TableHead>Memory Request</TableHead>
                  <TableHead>Memory Limit</TableHead>
                  <TableHead>Memory Usage</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {nodes.map((node: any) => (
                  <TableRow key={node.name}>
                    <TableCell className="font-mono font-medium">{node.name}</TableCell>
                    <TableCell className="font-mono">{node.cpu_request ?? '-'} Cores</TableCell>
                    <TableCell className="font-mono">{node.cpu_limit ?? '-'} Cores</TableCell>
                    <TableCell className={`font-mono ${getUsageColor(node.cpu_usage_percent)}`}>
                      {node.cpu_usage != null ? `${node.cpu_usage} Cores (${node.cpu_usage_percent}%)` : '-'}
                    </TableCell>
                    <TableCell className="font-mono">{formatBytes(node.memory_request)}</TableCell>
                    <TableCell className="font-mono">{formatBytes(node.memory_limit)}</TableCell>
                    <TableCell className={`font-mono ${getUsageColor(node.memory_usage_percent)}`}>
                      {node.memory_usage != null ? `${formatBytes(node.memory_usage)} (${node.memory_usage_percent}%)` : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Top Pods Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Top Pods 排行</CardTitle>
          <Select value={selectedNode} onValueChange={setSelectedNode}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="全部节点" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">全部节点</SelectItem>
              {nodes.map((node: any) => (
                <SelectItem key={node.name} value={node.name}>{node.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {topPodsLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* CPU Top 5 */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">CPU 消耗 Top 5</h3>
                {topPodsData?.cpuTop.length === 0 ? (
                  <div className="text-sm text-muted-foreground text-center py-4">暂无数据</div>
                ) : (
                  <div className="space-y-2">
                    {topPodsData?.cpuTop.map((pod: any, idx: number) => (
                      <div key={`cpu-${pod.name}-${pod.namespace}`} className="flex items-center gap-3 p-2 rounded-md border">
                        <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold ${
                          idx === 0 ? 'bg-warning/20 text-warning' :
                          idx === 1 ? 'bg-muted text-muted-foreground' :
                          idx === 2 ? 'bg-warning/10 text-warning/70' :
                          'bg-muted/50 text-muted-foreground'
                        }`}>
                          {idx + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="font-mono text-sm truncate">{pod.namespace}/{pod.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {pod.cpu_usage || pod.cpu_request} Cores
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Memory Top 5 */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">内存消耗 Top 5</h3>
                {topPodsData?.memoryTop.length === 0 ? (
                  <div className="text-sm text-muted-foreground text-center py-4">暂无数据</div>
                ) : (
                  <div className="space-y-2">
                    {topPodsData?.memoryTop.map((pod: any, idx: number) => (
                      <div key={`mem-${pod.name}-${pod.namespace}`} className="flex items-center gap-3 p-2 rounded-md border">
                        <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold ${
                          idx === 0 ? 'bg-warning/20 text-warning' :
                          idx === 1 ? 'bg-muted text-muted-foreground' :
                          idx === 2 ? 'bg-warning/10 text-warning/70' :
                          'bg-muted/50 text-muted-foreground'
                        }`}>
                          {idx + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="font-mono text-sm truncate">{pod.namespace}/{pod.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {formatBytes(pod.memory_usage || pod.memory_request)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default NodeMetricsView
