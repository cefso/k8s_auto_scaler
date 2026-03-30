import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { resourceApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ResourceTable } from '@/features/clusters/components/ResourceTable'
import {
  YamlDialog,
  ScaleDialog,
  LogsDialog,
  EventsDialog,
} from '@/features/clusters/components/ResourceDialogs'

export default function WorkloadDetailPage() {
  const { clusterId } = useParams<{ clusterId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const id = Number(clusterId)

  const kind = searchParams.get('kind') || 'Deployment'
  const namespace = searchParams.get('namespace') || ''
  const name = searchParams.get('name') || ''

  const resourceType = kind.toLowerCase() + 's'

  // Dialog states
  const [yamlDialog, setYamlDialog] = useState({ open: false, namespace, name })
  const [scaleDialog, setScaleDialog] = useState({ open: false, namespace, name, currentReplicas: 0 })
  const [logsDialog, setLogsDialog] = useState({ open: false, namespace, podName: '' })
  const [eventsDialog, setEventsDialog] = useState({ open: false, namespace, podName: '' })

  const { data: workload, isLoading: workloadLoading } = useQuery({
    queryKey: ['workload', id, resourceType, namespace, name],
    queryFn: () => {
      const apiMap: Record<string, any> = {
        deployments: () => resourceApi.deployments(id, namespace),
        statefulsets: () => resourceApi.statefulsets(id, namespace),
        rollouts: () => resourceApi.rollouts(id, namespace),
      }
      return apiMap[resourceType]?.().then((res: any) => {
        const items = res.data.items || []
        return items.find((item: any) => item.name === name)
      }) || Promise.resolve(null)
    },
    enabled: !!id && !!namespace && !!name,
  })

  const { data: pods = [], isLoading: podsLoading } = useQuery({
    queryKey: ['workload-pods', id, namespace, kind, name],
    queryFn: () => resourceApi.workloadPods(id, namespace, kind, name).then(res => res.data.items || []),
    enabled: !!id && !!namespace && !!name,
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => navigate(-1)}>返回</Button>
        <h1 className="text-xl font-bold">{kind}: {namespace}/{name}</h1>
        <div className="flex items-center gap-2 ml-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setYamlDialog({ open: true, namespace, name })}
          >
            YAML
          </Button>
          {['Deployment', 'StatefulSet', 'Rollout'].includes(kind) && (
            <Button
              variant="default"
              size="sm"
              onClick={() => setScaleDialog({ open: true, namespace, name, currentReplicas: workload?.replicas ?? 0 })}
            >
              扩缩容
            </Button>
          )}
        </div>
      </div>

      {/* Workload Info */}
      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent>
          {workloadLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : workload ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">命名空间</div>
                <div className="font-mono">{workload.namespace}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">副本数</div>
                <div className="font-mono">{workload.replicas ?? '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">就绪副本</div>
                <div className="font-mono">{workload.ready_replicas ?? '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">状态</div>
                <Badge variant="secondary">{workload.status || '-'}</Badge>
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">未找到工作负载信息</div>
          )}
        </CardContent>
      </Card>

      {/* Pods */}
      <Card>
        <CardHeader>
          <CardTitle>Pods ({pods.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {podsLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : (
            <ResourceTable
              items={pods}
              resourceType="pods"
              onAction={(action, item) => {
                if (action === 'yaml') {
                  setYamlDialog({ open: true, namespace: item.namespace || '', name: item.name })
                } else if (action === 'logs') {
                  setLogsDialog({ open: true, namespace: item.namespace || '', podName: item.name })
                } else if (action === 'events') {
                  setEventsDialog({ open: true, namespace: item.namespace || '', podName: item.name })
                }
              }}
            />
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      <YamlDialog
        clusterId={id}
        resourceType="pods"
        namespace={yamlDialog.namespace}
        name={yamlDialog.name}
        open={yamlDialog.open}
        onOpenChange={(open) => setYamlDialog({ ...yamlDialog, open })}
      />

      <ScaleDialog
        clusterId={id}
        namespace={scaleDialog.namespace}
        name={scaleDialog.name}
        resourceType={kind as any}
        currentReplicas={scaleDialog.currentReplicas}
        open={scaleDialog.open}
        onOpenChange={(open) => setScaleDialog({ ...scaleDialog, open })}
        onSuccess={() => {
          // Refresh data
        }}
      />

      <LogsDialog
        clusterId={id}
        namespace={logsDialog.namespace}
        podName={logsDialog.podName}
        open={logsDialog.open}
        onOpenChange={(open) => setLogsDialog({ ...logsDialog, open })}
      />

      <EventsDialog
        clusterId={id}
        namespace={eventsDialog.namespace}
        podName={eventsDialog.podName}
        open={eventsDialog.open}
        onOpenChange={(open) => setEventsDialog({ ...eventsDialog, open })}
      />
    </div>
  )
}
