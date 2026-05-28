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
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

interface NodeMetricsViewProps {
  clusterId: number
}

/** 名称含 virtual 的节点不参与集群 CPU/内存总量汇总 */
function isPhysicalNode(node: { name: string; is_virtual?: boolean }) {
  return node.is_virtual !== true && !node.name.toLowerCase().includes('virtual')
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
  const physicalNodes = nodes.filter(isPhysicalNode)

  // 集群汇总：真实使用 / 节点总 capacity（排除 virtual 节点）
  const totalCpuNum = physicalNodes.reduce((sum: number, n: any) => sum + (n.cpu_capacity || 0), 0)
  const usedCpuNum = physicalNodes.reduce((sum: number, n: any) => sum + (n.cpu_usage || 0), 0)
  const totalMemory = physicalNodes.reduce((sum: number, n: any) => sum + (n.memory_capacity || 0), 0)
  const usedMemory = physicalNodes.reduce((sum: number, n: any) => sum + (n.memory_usage || 0), 0)
  const totalCpu = totalCpuNum.toFixed(2)
  const usedCpu = usedCpuNum.toFixed(2)

  const cpuPercent = totalCpuNum > 0
    ? Math.round((usedCpuNum / totalCpuNum) * 100)
    : 0
  const memoryPercent = totalMemory > 0
    ? Math.round((usedMemory / totalMemory) * 100)
    : 0

  // 当前选中节点的数据（选具体节点时仍展示该节点自身 usage/capacity）
  const selectedNodeData = selectedNode === '__all__'
    ? null
    : nodes.find((n: any) => n.name === selectedNode)
  const nodeCpuPercent = selectedNodeData?.cpu_percent ?? cpuPercent
  const nodeMemoryPercent = selectedNodeData?.memory_percent ?? memoryPercent
  const nodeCpuUsage = selectedNodeData?.cpu_usage ?? usedCpu
  const nodeMemUsage = selectedNodeData?.memory_usage ?? usedMemory
  const nodeCpuTotal = selectedNodeData?.cpu_capacity ?? totalCpu
  const nodeMemTotal = selectedNodeData?.memory_capacity ?? totalMemory

  // 环形图数据
  const cpuChartData = [
    { name: '已用', value: Number(usedCpu), percent: cpuPercent },
    { name: '剩余', value: Math.max(0, Number(totalCpu) - Number(usedCpu)), percent: 100 - cpuPercent },
  ]
  const memoryChartData = [
    { name: '已用', value: usedMemory, percent: memoryPercent },
    { name: '剩余', value: Math.max(0, totalMemory - usedMemory), percent: 100 - memoryPercent },
  ]

  const getUsageColor = (usage?: number) => {
    if (usage === undefined || usage === null) return ''
    if (usage >= 90) return 'text-red-500'
    if (usage >= 70) return 'text-yellow-500'
    return 'text-green-500'
  }

  const getBarColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500'
    if (percent >= 70) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  const getChartColor = (percent: number) => {
    if (percent >= 90) return '#ef4444' // red-500
    if (percent >= 70) return '#f59e0b' // amber-500
    return '#22c55e' // green-500
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards with Charts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 节点数 Card */}
        <Card className="flex flex-col">
          <CardContent className="p-2 text-center">
            <div className="text-sm text-muted-foreground">节点数（不含 virtual）</div>
          </CardContent>
          <CardContent className="flex-1 p-2 flex items-center justify-center">
            <span className="text-4xl font-bold font-mono">{physicalNodes.length || '-'}</span>
          </CardContent>
        </Card>

        {/* CPU Chart */}
        <Card>
          <CardContent className="p-2 text-center">
            <div className="text-sm text-muted-foreground">CPU 使用率</div>
          </CardContent>
          <CardContent className="p-2">
            <div className="h-[80px] relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={cpuChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={25}
                    outerRadius={38}
                    dataKey="value"
                    stroke="none"
                  >
                    <Cell fill={getChartColor(cpuPercent)} />
                    <Cell fill="#e5e7eb" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-lg font-bold ${getUsageColor(cpuPercent)}`}>{cpuPercent}%</span>
              </div>
            </div>
            <div className="text-xs text-muted-foreground text-center">
              {usedCpu} / {totalCpu} Cores
            </div>
          </CardContent>
        </Card>

        {/* Memory Chart */}
        <Card>
          <CardContent className="p-2 text-center">
            <div className="text-sm text-muted-foreground">内存使用率</div>
          </CardContent>
          <CardContent className="p-2">
            <div className="h-[80px] relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={memoryChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={25}
                    outerRadius={38}
                    dataKey="value"
                    stroke="none"
                  >
                    <Cell fill={getChartColor(memoryPercent)} />
                    <Cell fill="#e5e7eb" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-lg font-bold ${getUsageColor(memoryPercent)}`}>{memoryPercent}%</span>
              </div>
            </div>
            <div className="text-xs text-muted-foreground text-center">
              {formatBytes(usedMemory)} / {formatBytes(totalMemory)}
            </div>
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
                    <TableCell>
                      {node.cpu_percent != null ? (
                        <div className="space-y-1">
                          <div className="text-xs font-mono">{node.cpu_usage} Cores</div>
                          <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                            <div
                              className={`h-2 rounded-full ${getBarColor(node.cpu_percent)}`}
                              style={{ width: `${Math.min(node.cpu_percent, 100)}%` }}
                            />
                          </div>
                          <div className={`text-xs font-mono ${getUsageColor(node.cpu_percent)}`}>{node.cpu_percent}%</div>
                        </div>
                      ) : '-'}
                    </TableCell>
                    <TableCell className="font-mono">{formatBytes(node.memory_request)}</TableCell>
                    <TableCell className="font-mono">{formatBytes(node.memory_limit)}</TableCell>
                    <TableCell>
                      {node.memory_percent != null ? (
                        <div className="space-y-1">
                          <div className="text-xs font-mono">{formatBytes(node.memory_usage)}</div>
                          <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                            <div
                              className={`h-2 rounded-full ${getBarColor(node.memory_percent)}`}
                              style={{ width: `${Math.min(node.memory_percent, 100)}%` }}
                            />
                          </div>
                          <div className={`text-xs font-mono ${getUsageColor(node.memory_percent)}`}>{node.memory_percent}%</div>
                        </div>
                      ) : '-'}
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
            <div className="space-y-4">
              {/* 节点资源环形图 */}
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardContent className="p-2 text-center">
                    <div className="text-sm text-muted-foreground">CPU 使用率</div>
                  </CardContent>
                  <CardContent className="p-2">
                    <div className="h-[80px] relative">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[{ name: '已用', value: Number(nodeCpuUsage) }, { name: '剩余', value: Math.max(0, Number(nodeCpuTotal) - Number(nodeCpuUsage)) }]}
                            cx="50%"
                            cy="50%"
                            innerRadius={25}
                            outerRadius={38}
                            dataKey="value"
                            stroke="none"
                          >
                            <Cell fill={getChartColor(nodeCpuPercent)} />
                            <Cell fill="#e5e7eb" />
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className={`text-lg font-bold ${getUsageColor(nodeCpuPercent)}`}>{nodeCpuPercent}%</span>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-center">
                      {nodeCpuUsage} / {nodeCpuTotal} Cores
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-2 text-center">
                    <div className="text-sm text-muted-foreground">内存使用率</div>
                  </CardContent>
                  <CardContent className="p-2">
                    <div className="h-[80px] relative">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[{ name: '已用', value: nodeMemUsage }, { name: '剩余', value: Math.max(0, nodeMemTotal - nodeMemUsage) }]}
                            cx="50%"
                            cy="50%"
                            innerRadius={25}
                            outerRadius={38}
                            dataKey="value"
                            stroke="none"
                          >
                            <Cell fill={getChartColor(nodeMemoryPercent)} />
                            <Cell fill="#e5e7eb" />
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className={`text-lg font-bold ${getUsageColor(nodeMemoryPercent)}`}>{nodeMemoryPercent}%</span>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-center">
                      {formatBytes(nodeMemUsage)} / {formatBytes(nodeMemTotal)}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Top Pods Lists */}
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
                            {pod.cpu_usage != null ? `${pod.cpu_usage}C` : '-'} / {pod.cpu_limit != null ? `${pod.cpu_limit}C` : '-'}
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
                            {pod.memory_usage != null ? formatBytes(pod.memory_usage) : '-'} / {pod.memory_limit != null ? formatBytes(pod.memory_limit) : '-'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default NodeMetricsView
