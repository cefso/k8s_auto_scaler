import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clusterApi, type Cluster } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Loader2, PlusIcon, Trash2, RefreshCw, CheckCircle, XCircle, FileCode } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ClusterListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [addError, setAddError] = useState('')
  const [testingId, setTestingId] = useState<number | null>(null)
  const [updateKubeconfigId, setUpdateKubeconfigId] = useState<number | null>(null)

  const { data: clusters = [], isLoading, error } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => clusterApi.list().then(res => res.data),
  })

  const createMutation = useMutation({
    mutationFn: clusterApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
      setShowAddModal(false)
    },
    onError: (err: any) => {
      setAddError(err.response?.data?.detail || '添加失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: clusterApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
  })

  const testMutation = useMutation({
    mutationFn: clusterApi.test,
    onSuccess: () => {
      alert('连接成功')
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
    onError: (err: any) => {
      alert('连接失败: ' + (err.response?.data?.detail || err.message))
    },
    onSettled: () => {
      setTestingId(null)
    },
  })

  const updateKubeconfigMutation = useMutation({
    mutationFn: ({ id, kubeconfig }: { id: number; kubeconfig: string }) =>
      clusterApi.updateKubeconfig(id, kubeconfig),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
      setUpdateKubeconfigId(null)
      alert('更新成功')
    },
    onError: (err: any) => {
      alert('更新失败: ' + (err.response?.data?.detail || err.message))
    },
  })

  const handleTest = (id: number) => {
    setTestingId(id)
    testMutation.mutate(id)
  }

  const handleDelete = (cluster: Cluster) => {
    if (confirm(`确定要删除集群 "${cluster.display_name || cluster.name}" 吗？`)) {
      deleteMutation.mutate(cluster.id)
    }
  }

  const handleRowClick = (cluster: Cluster) => {
    navigate(`/cluster/${cluster.id}`)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-error">
        加载失败: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">集群管理</h1>
        <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
          <DialogTrigger asChild>
            <Button>
              <PlusIcon className="h-4 w-4 mr-2" />
              添加集群
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加集群</DialogTitle>
            </DialogHeader>
            <AddClusterForm
              onSubmit={(data) => createMutation.mutate(data)}
              isLoading={createMutation.isPending}
              error={addError}
            />
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clusters.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    暂无集群，点击上方添加按钮添加
                  </TableCell>
                </TableRow>
              ) : (
                clusters.map((cluster) => (
                  <TableRow
                    key={cluster.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleRowClick(cluster)}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {cluster.is_active ? (
                          <CheckCircle className="h-4 w-4 text-success" />
                        ) : (
                          <XCircle className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span>{cluster.display_name || cluster.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={cluster.is_active ? 'default' : 'secondary'}>
                        {cluster.is_active ? '活跃' : '禁用'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(cluster.created_at).toLocaleString('zh-CN')}
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTest(cluster.id)}
                          disabled={testingId === cluster.id}
                        >
                          <RefreshCw className={cn('h-4 w-4', testingId === cluster.id && 'animate-spin')} />
                          测试连接
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setUpdateKubeconfigId(cluster.id)}
                        >
                          <FileCode className="h-4 w-4" />
                          更新kubeconfig
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(cluster)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
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

      {/* Update Kubeconfig Dialog */}
      <Dialog open={updateKubeconfigId !== null} onOpenChange={(open) => !open && setUpdateKubeconfigId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>更新 Kubeconfig</DialogTitle>
          </DialogHeader>
          <UpdateKubeconfigForm
            onSubmit={(kubeconfig) => updateKubeconfigMutation.mutate({ id: updateKubeconfigId!, kubeconfig })}
            isLoading={updateKubeconfigMutation.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

interface AddClusterFormProps {
  onSubmit: (data: { name: string; display_name?: string; kubeconfig_content: string }) => void
  isLoading: boolean
  error: string
}

function AddClusterForm({ onSubmit, isLoading, error }: AddClusterFormProps) {
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [kubeconfig, setKubeconfig] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      name,
      display_name: displayName || undefined,
      kubeconfig_content: kubeconfig,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="text-sm text-error bg-error/10 p-3 rounded-md">{error}</div>
      )}
      <div className="space-y-2">
        <Label htmlFor="name">集群名称 *</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="例如: production-cluster"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="displayName">显示名称</Label>
        <Input
          id="displayName"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="可选，用于展示"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="kubeconfig">Kubeconfig *</Label>
        <textarea
          id="kubeconfig"
          value={kubeconfig}
          onChange={(e) => setKubeconfig(e.target.value)}
          placeholder="粘贴 kubeconfig 内容"
          className="w-full h-40 px-3 py-2 rounded-md border border-input bg-background text-sm font-mono"
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        添加
      </Button>
    </form>
  )
}

interface UpdateKubeconfigFormProps {
  onSubmit: (kubeconfig: string) => void
  isLoading: boolean
}

function UpdateKubeconfigForm({ onSubmit, isLoading }: UpdateKubeconfigFormProps) {
  const [kubeconfig, setKubeconfig] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(kubeconfig)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="kubeconfig">Kubeconfig *</Label>
        <textarea
          id="kubeconfig"
          value={kubeconfig}
          onChange={(e) => setKubeconfig(e.target.value)}
          placeholder="粘贴新的 kubeconfig 内容"
          className="w-full h-40 px-3 py-2 rounded-md border border-input bg-background text-sm font-mono"
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        更新
      </Button>
    </form>
  )
}
