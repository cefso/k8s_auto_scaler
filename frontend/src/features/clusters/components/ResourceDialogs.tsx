import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { resourceApi, scalingApi, eventsApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { YamlViewer } from '@/components/YamlViewer'
import { LogViewer } from '@/components/LogViewer'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'

// YAML 查看弹窗
interface YamlDialogProps {
  clusterId: number
  resourceType: string
  namespace: string
  name: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function YamlDialog({ clusterId, resourceType, namespace, name, open, onOpenChange }: YamlDialogProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['yaml', clusterId, resourceType, namespace, name],
    queryFn: () => resourceApi.getYaml(clusterId, resourceType, namespace, name).then(res => res.data.yaml),
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-mono">{namespace}/{name}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : data ? (
          <ScrollArea className="flex-1">
            <YamlViewer yaml={data} className="max-h-[60vh]" />
          </ScrollArea>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

// 扩缩容弹窗
interface ScaleDialogProps {
  clusterId: number
  namespace: string
  name: string
  resourceType: 'Deployment' | 'StatefulSet' | 'Rollout'
  currentReplicas: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function ScaleDialog({ clusterId, namespace, name, resourceType, currentReplicas, open, onOpenChange, onSuccess }: ScaleDialogProps) {
  const [replicas, setReplicas] = useState(currentReplicas)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => scalingApi.scale(clusterId, {
      namespace,
      resource_type: resourceType,
      resource_name: name,
      replicas,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resources', clusterId] })
      onOpenChange(false)
      onSuccess?.()
    },
    onError: (err: any) => {
      alert('扩缩容失败: ' + (err.response?.data?.detail || err.message))
    },
  })

  const handleSubmit = () => {
    mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>扩缩容</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">
            {resourceType}: {namespace}/{name}
          </div>
          <div className="space-y-2">
            <Label>目标副本数</Label>
            <Input
              type="number"
              min="0"
              value={replicas}
              onChange={(e) => setReplicas(Number(e.target.value))}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button onClick={handleSubmit} disabled={mutation.isPending}>
              {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              确认
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// 日志查看弹窗
interface LogsDialogProps {
  clusterId: number
  namespace: string
  podName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function LogsDialog({ clusterId, namespace, podName, open, onOpenChange }: LogsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-mono">日志 - {namespace}/{podName}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 min-h-0">
          <LogViewer
            clusterId={clusterId}
            namespace={namespace}
            podName={podName}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

// 事件弹窗
interface EventsDialogProps {
  clusterId: number
  namespace: string
  podName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EventsDialog({ clusterId, namespace, podName, open, onOpenChange }: EventsDialogProps) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ['pod-events', clusterId, namespace, podName],
    queryFn: () => eventsApi.getPodEvents(clusterId, namespace, podName).then(res => res.data.items || []),
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-mono">Pod 事件 - {namespace}/{podName}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : events.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">暂无事件</div>
        ) : (
          <ScrollArea className="flex-1">
            <div className="space-y-3 p-2">
              {events.map((event: any, index: number) => (
                <div
                  key={index}
                  className={`p-3 rounded-md border ${
                    event.type === 'Warning' ? 'border-error/50 bg-error/5' : 'border-border'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={event.type === 'Warning' ? 'destructive' : 'secondary'}>
                      {event.type}
                    </Badge>
                    <span className="font-medium text-sm">{event.reason || '-'}</span>
                    <span className="text-xs text-muted-foreground ml-auto">{event.age || event.last_timestamp || ''}</span>
                  </div>
                  <div className="text-sm">{event.message || '-'}</div>
                  <div className="text-xs text-muted-foreground mt-1">来源: {event.source || '-'}</div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}

// Helm Values 弹窗
interface HelmValuesDialogProps {
  clusterId: number
  namespace: string
  name: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function HelmValuesDialog({ clusterId, namespace, name, open, onOpenChange }: HelmValuesDialogProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['helm-values', clusterId, namespace, name],
    queryFn: () => resourceApi.helmGetValues(clusterId, namespace, name).then(res => res.data.values || '# 无 values 内容'),
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-mono">Helm Values - {namespace}/{name}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <ScrollArea className="flex-1">
            <pre className="p-4 bg-muted rounded-md font-mono text-sm whitespace-pre-wrap">
              {data}
            </pre>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
