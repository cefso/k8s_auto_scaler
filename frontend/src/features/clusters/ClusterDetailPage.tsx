import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { clusterApi, resourceApi, batchApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DashboardView } from '@/features/dashboard/DashboardView'
import { NodeMetricsView } from '@/features/dashboard/NodeMetricsView'
import { ResourceTable } from './components/ResourceTable'
import type { ResourceTableItem } from './components/ResourceTable'
import {
  YamlDialog,
  ScaleDialog,
  LogsDialog,
  EventsDialog,
  HelmValuesDialog,
} from './components/ResourceDialogs'
import { BatchConfirmDialog, UpdateLabelsDialog } from './components/BatchActionDialog'

const hasNamespaceFilter = [
  'deployments', 'statefulsets', 'rollouts', 'pods', 'services', 'ingresses',
  'ingressroutes', 'ingressroutetcps', 'ingressrouteudps', 'apisixroutes',
  'apisixtlses', 'configmaps', 'secrets', 'hpas'
]

export default function ClusterDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const clusterId = Number(id)
  const queryClient = useQueryClient()

  const activeTab = searchParams.get('tab') || 'dashboard'

  // Batch dialog state
  const [batchDialog, setBatchDialog] = useState<{
    open: boolean
    action: 'restart' | 'delete' | 'updateLabels'
    items: { namespace: string; name: string }[]
  }>({
    open: false,
    action: 'restart',
    items: [],
  })
  const filterNs = searchParams.get('namespace') || ''

  // Dialog states
  const [yamlDialog, setYamlDialog] = useState<{ open: boolean; resourceType: string; namespace: string; name: string }>({
    open: false,
    resourceType: '',
    namespace: '',
    name: '',
  })
  const [scaleDialog, setScaleDialog] = useState<{ open: boolean; namespace: string; name: string; resourceType: 'Deployment' | 'StatefulSet' | 'Rollout'; currentReplicas: number }>({
    open: false,
    namespace: '',
    name: '',
    resourceType: 'Deployment',
    currentReplicas: 0,
  })
  const [logsDialog, setLogsDialog] = useState<{ open: boolean; namespace: string; podName: string }>({
    open: false,
    namespace: '',
    podName: '',
  })
  const [eventsDialog, setEventsDialog] = useState<{ open: boolean; namespace: string; podName: string }>({
    open: false,
    namespace: '',
    podName: '',
  })
  const [helmValuesDialog, setHelmValuesDialog] = useState<{ open: boolean; namespace: string; name: string }>({
    open: false,
    namespace: '',
    name: '',
  })

  const { data: cluster, isLoading: clusterLoading } = useQuery({
    queryKey: ['cluster', clusterId],
    queryFn: () => clusterApi.get(clusterId).then(res => res.data),
    enabled: !!clusterId,
  })

  const { data: namespaces = [], isLoading: nsLoading } = useQuery({
    queryKey: ['namespaces', clusterId],
    queryFn: () => resourceApi.namespaces(clusterId).then(res => res.data.items),
    enabled: !!clusterId && hasNamespaceFilter.includes(activeTab),
  })

  const handleNamespaceChange = (ns: string) => {
    setSearchParams({ tab: activeTab, namespace: ns === '__all__' ? '' : ns })
  }

  if (clusterLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with namespace filter */}
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold">{cluster?.display_name || cluster?.name}</h1>
        <div className="flex items-center gap-2 ml-auto">
          {hasNamespaceFilter.includes(activeTab) && !nsLoading && (
            <Select value={filterNs || '__all__'} onValueChange={handleNamespaceChange}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="全部命名空间" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">全部命名空间</SelectItem>
                {namespaces.map((ns: any) => (
                  <SelectItem key={ns.name} value={ns.name}>{ns.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>刷新</Button>
        </div>
      </div>

      {/* Content - determined by sidebar navigation */}
      <ClusterTabContent clusterId={clusterId} tab={activeTab} namespace={filterNs} onAction={handleAction} onBatchAction={handleBatchAction} />

      {/* Dialogs */}
      <YamlDialog
        clusterId={clusterId}
        resourceType={yamlDialog.resourceType}
        namespace={yamlDialog.namespace}
        name={yamlDialog.name}
        open={yamlDialog.open}
        onOpenChange={(open) => setYamlDialog({ ...yamlDialog, open })}
      />

      <ScaleDialog
        clusterId={clusterId}
        namespace={scaleDialog.namespace}
        name={scaleDialog.name}
        resourceType={scaleDialog.resourceType}
        currentReplicas={scaleDialog.currentReplicas}
        open={scaleDialog.open}
        onOpenChange={(open) => setScaleDialog({ ...scaleDialog, open })}
      />

      <LogsDialog
        clusterId={clusterId}
        namespace={logsDialog.namespace}
        podName={logsDialog.podName}
        open={logsDialog.open}
        onOpenChange={(open) => setLogsDialog({ ...logsDialog, open })}
      />

      <EventsDialog
        clusterId={clusterId}
        namespace={eventsDialog.namespace}
        podName={eventsDialog.podName}
        open={eventsDialog.open}
        onOpenChange={(open) => setEventsDialog({ ...eventsDialog, open })}
      />

      <HelmValuesDialog
        clusterId={clusterId}
        namespace={helmValuesDialog.namespace}
        name={helmValuesDialog.name}
        open={helmValuesDialog.open}
        onOpenChange={(open) => setHelmValuesDialog({ ...helmValuesDialog, open })}
      />

      <BatchConfirmDialog
        open={batchDialog.open && batchDialog.action !== 'updateLabels'}
        onOpenChange={(open) => setBatchDialog({ ...batchDialog, open })}
        action={batchDialog.action === 'delete' ? 'delete' : 'restart'}
        items={batchDialog.items}
        onConfirm={handleBatchConfirm}
      />

      <UpdateLabelsDialog
        open={batchDialog.open && batchDialog.action === 'updateLabels'}
        onOpenChange={(open) => setBatchDialog({ ...batchDialog, open })}
        items={batchDialog.items}
        onConfirm={handleUpdateLabelsConfirm}
      />
    </div>
  )

  function handleAction(action: string, item: ResourceTableItem) {
    switch (action) {
      case 'yaml':
        setYamlDialog({
          open: true,
          resourceType: activeTab,
          namespace: item.namespace || '',
          name: item.name,
        })
        break
      case 'scale':
        setScaleDialog({
          open: true,
          namespace: item.namespace || '',
          name: item.name,
          resourceType: activeTab === 'deployments' ? 'Deployment' : activeTab === 'statefulsets' ? 'StatefulSet' : 'Rollout',
          currentReplicas: item.replicas ?? 0,
        })
        break
      case 'detail':
        navigate(`/cluster/${clusterId}/workload?kind=${activeTab === 'deployments' ? 'Deployment' : activeTab === 'statefulsets' ? 'StatefulSet' : 'Rollout'}&namespace=${item.namespace}&name=${item.name}`)
        break
      case 'logs':
        setLogsDialog({
          open: true,
          namespace: item.namespace || '',
          podName: item.name,
        })
        break
      case 'events':
        setEventsDialog({
          open: true,
          namespace: item.namespace || '',
          podName: item.name,
        })
        break
      case 'values':
        setHelmValuesDialog({
          open: true,
          namespace: item.namespace || '',
          name: item.name,
        })
        break
    }
  }

  function handleBatchAction(action: string, items: { namespace: string; name: string }[]) {
    setBatchDialog({ open: true, action: action as 'restart' | 'delete' | 'updateLabels', items })
  }

  async function handleBatchConfirm() {
    const { action, items } = batchDialog
    if (action === 'restart') {
      await batchApi.restartPods(clusterId, items)
    } else if (action === 'delete') {
      await batchApi.deletePods(clusterId, items)
    } else if (action === 'updateLabels') {
      // updateLabels needs special handling with labels, handled in UpdateLabelsDialog
      return
    }
    queryClient.invalidateQueries({ queryKey: ['resources', clusterId, 'pods'] })
  }

  async function handleUpdateLabelsConfirm(labels: Record<string, string>) {
    await batchApi.updateLabels(clusterId, batchDialog.items, labels)
    queryClient.invalidateQueries({ queryKey: ['resources', clusterId, 'pods'] })
  }
}

interface ClusterTabContentProps {
  clusterId: number
  tab: string
  namespace: string
  onAction: (action: string, item: ResourceTableItem) => void
  onBatchAction?: (action: string, items: { namespace: string; name: string }[]) => void
}

function ClusterTabContent({ clusterId, tab, namespace, onAction, onBatchAction }: ClusterTabContentProps) {
  const ns = namespace || undefined
  const isResourceTab = tab !== 'dashboard' && tab !== 'nodes'

  const { data, isLoading } = useQuery({
    queryKey: ['resources', clusterId, tab, ns],
    queryFn: () => {
      const apiMap: Record<string, any> = {
        deployments: () => resourceApi.deployments(clusterId, ns),
        statefulsets: () => resourceApi.statefulsets(clusterId, ns),
        rollouts: () => resourceApi.rollouts(clusterId, ns),
        pods: () => resourceApi.pods(clusterId, ns),
        services: () => resourceApi.services(clusterId, ns),
        ingresses: () => resourceApi.ingresses(clusterId, ns),
        ingressroutes: () => resourceApi.ingressroutes(clusterId, ns),
        ingressroutetcps: () => resourceApi.ingressroutetcps(clusterId, ns),
        ingressrouteudps: () => resourceApi.ingressrouteudps(clusterId, ns),
        apisixroutes: () => resourceApi.apisixroutes(clusterId, ns),
        apisixtlses: () => resourceApi.apisixtlses(clusterId, ns),
        configmaps: () => resourceApi.configmaps(clusterId, ns),
        secrets: () => resourceApi.secrets(clusterId, ns),
        hpas: () => resourceApi.hpas(clusterId, ns),
        helm: () => resourceApi.helm(clusterId, ns),
      }
      const fn = apiMap[tab]
      return fn ? fn().then((res: any) => res.data) : Promise.resolve({ items: [] })
    },
    enabled: !!clusterId && isResourceTab,
  })

  if (tab === 'dashboard') {
    return <DashboardView clusterId={clusterId} />
  }

  if (tab === 'nodes') {
    return <NodeMetricsView clusterId={clusterId} />
  }

  if (isLoading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
  }

  const items = data?.items || []

  return <ResourceTable items={items} resourceType={tab} onAction={onAction} onBatchAction={onBatchAction} />
}
