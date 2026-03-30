import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scalingApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

export default function ScheduleListPage() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)

  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => scalingApi.listSchedules().then(res => res.data),
  })

  const deleteMutation = useMutation({
    mutationFn: scalingApi.deleteSchedule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, isEnabled }: { id: number; isEnabled: boolean }) =>
      scalingApi.updateSchedule(id, { is_enabled: isEnabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">定时扩缩容</h1>
        <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
          <DialogTrigger asChild>
            <Button>添加定时任务</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加定时任务</DialogTitle>
            </DialogHeader>
            <ScheduleForm onSuccess={() => setShowAddModal(false)} />
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>集群</TableHead>
                <TableHead>命名空间</TableHead>
                <TableHead>资源</TableHead>
                <TableHead>目标副本</TableHead>
                <TableHead>Cron 表达式</TableHead>
                <TableHead>时区</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>描述</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedules.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                    暂无定时任务
                  </TableCell>
                </TableRow>
              ) : (
                schedules.map((schedule) => (
                  <TableRow key={schedule.id}>
                    <TableCell>{schedule.cluster_id}</TableCell>
                    <TableCell className="font-mono text-sm">{schedule.namespace}</TableCell>
                    <TableCell>
                      {schedule.resource_type}/{schedule.resource_name}
                    </TableCell>
                    <TableCell>{schedule.target_replicas}</TableCell>
                    <TableCell className="font-mono">{schedule.cron_expression}</TableCell>
                    <TableCell>{schedule.timezone}</TableCell>
                    <TableCell>
                      <Badge variant={schedule.is_enabled ? 'default' : 'secondary'}>
                        {schedule.is_enabled ? '启用' : '禁用'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground max-w-48 truncate">
                      {schedule.description || '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleMutation.mutate({ id: schedule.id, isEnabled: !schedule.is_enabled })}
                        >
                          {schedule.is_enabled ? '禁用' : '启用'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (confirm('确定要删除此任务吗？')) {
                              deleteMutation.mutate(schedule.id)
                            }
                          }}
                        >
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function ScheduleForm({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState({
    cluster_id: 0,
    namespace: '',
    resource_type: 'Deployment',
    resource_name: '',
    target_replicas: 1,
    cron_expression: '0 9 * * 1-5',
    timezone: 'Asia/Shanghai',
    description: '',
    is_enabled: true,
  })

  const mutation = useMutation({
    mutationFn: scalingApi.createSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] })
      onSuccess()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label>集群 ID</Label>
        <Input
          type="number"
          value={formData.cluster_id}
          onChange={(e) => setFormData({ ...formData, cluster_id: Number(e.target.value) })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>命名空间</Label>
        <Input
          value={formData.namespace}
          onChange={(e) => setFormData({ ...formData, namespace: e.target.value })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>资源类型</Label>
        <Input
          value={formData.resource_type}
          onChange={(e) => setFormData({ ...formData, resource_type: e.target.value })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>资源名称</Label>
        <Input
          value={formData.resource_name}
          onChange={(e) => setFormData({ ...formData, resource_name: e.target.value })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>目标副本数</Label>
        <Input
          type="number"
          min="0"
          value={formData.target_replicas}
          onChange={(e) => setFormData({ ...formData, target_replicas: Number(e.target.value) })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>Cron 表达式</Label>
        <Input
          value={formData.cron_expression}
          onChange={(e) => setFormData({ ...formData, cron_expression: e.target.value })}
          placeholder="0 9 * * 1-5"
          required
        />
      </div>
      <div className="space-y-2">
        <Label>时区</Label>
        <Input
          value={formData.timezone}
          onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
        />
      </div>
      <div className="space-y-2">
        <Label>描述</Label>
        <Input
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
        />
      </div>
      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        创建
      </Button>
    </form>
  )
}
