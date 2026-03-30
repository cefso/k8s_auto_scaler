import { useMemo, useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Loader2, RotateCw, Trash2, Tags, X } from 'lucide-react'

export interface ResourceTableItem {
  name: string
  namespace?: string
  [key: string]: any
}

interface ResourceTableProps {
  items: any[]
  resourceType: string
  isLoading?: boolean
  onAction?: (action: string, item: ResourceTableItem) => void
  onBatchAction?: (action: string, items: { namespace: string; name: string }[]) => void
}

export function ResourceTable({ items, resourceType, isLoading, onAction, onBatchAction }: ResourceTableProps) {
  const columns = useMemo(() => getColumnsForType(resourceType), [resourceType])
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())

  const isSelectable = resourceType === 'pods' && !!onBatchAction

  const toggleItem = (namespace: string, name: string) => {
    const key = `${namespace}/${name}`
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleAll = () => {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(items.map(item => `${item.namespace}/${item.name}`)))
    }
  }

  const clearSelection = () => setSelectedItems(new Set())

  const selectedCount = selectedItems.size
  const allSelected = items.length > 0 && selectedItems.size === items.length

  if (isLoading) {
    return <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  if (!items || items.length === 0) {
    return <div className="text-center text-muted-foreground py-8">暂无数据</div>
  }

  return (
    <div className="space-y-2">
      {isSelectable && selectedCount > 0 && (
        <BatchToolbar
          selectedCount={selectedCount}
          onRestart={() => onBatchAction?.('restart', Array.from(selectedItems).map(key => {
            const [namespace, name] = key.split('/')
            return { namespace, name }
          }))}
          onDelete={() => onBatchAction?.('delete', Array.from(selectedItems).map(key => {
            const [namespace, name] = key.split('/')
            return { namespace, name }
          }))}
          onUpdateLabels={() => onBatchAction?.('updateLabels', Array.from(selectedItems).map(key => {
            const [namespace, name] = key.split('/')
            return { namespace, name }
          }))}
          onClear={clearSelection}
        />
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {isSelectable && (
                <TableHead className="w-10">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
                </TableHead>
              )}
              {columns.map((col) => (
                <TableHead key={col.key} className={col.className}>
                  {col.label}
                </TableHead>
              ))}
              {onAction && <TableHead className="text-center w-32">操作</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, index) => {
              const itemKey = `${item.namespace}/${item.name}`
              const isSelected = selectedItems.has(itemKey)
              return (
                <TableRow key={`${item.name}-${item.namespace}-${index}`} data-selected={isSelected}>
                  {isSelectable && (
                    <TableCell className="w-10">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleItem(item.namespace || '', item.name)}
                      />
                    </TableCell>
                  )}
                  {columns.map((col) => (
                    <TableCell key={col.key} className={col.cellClassName}>
                      {col.render ? col.render(item) : item[col.key] ?? '-'}
                    </TableCell>
                  ))}
                  {onAction && (
                    <TableCell className="text-center">
                      <ActionButtons resourceType={resourceType} item={item} onAction={onAction} />
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

interface ActionButtonsProps {
  resourceType: string
  item: ResourceTableItem
  onAction: (action: string, item: ResourceTableItem) => void
}

function ActionButtons({ resourceType, item, onAction }: ActionButtonsProps) {
  const buttons: { label: string; action: string; variant?: 'default' | 'secondary' | 'outline' | 'destructive' }[] = []

  if (resourceType === 'pods') {
    buttons.push({ label: '日志', action: 'logs', variant: 'outline' })
    buttons.push({ label: '事件', action: 'events', variant: 'outline' })
    buttons.push({ label: 'YAML', action: 'yaml', variant: 'outline' })
  } else if (['deployments', 'statefulsets', 'rollouts'].includes(resourceType)) {
    buttons.push({ label: '详情', action: 'detail', variant: 'outline' })
    buttons.push({ label: '扩缩容', action: 'scale', variant: 'default' })
    buttons.push({ label: 'YAML', action: 'yaml', variant: 'outline' })
  } else if (resourceType === 'helm') {
    buttons.push({ label: 'Values', action: 'values', variant: 'outline' })
  } else {
    buttons.push({ label: 'YAML', action: 'yaml', variant: 'outline' })
  }

  return (
    <div className="flex items-center justify-center gap-1">
      {buttons.map((btn) => (
        <Button
          key={btn.action}
          variant={btn.variant || 'outline'}
          size="sm"
          onClick={() => onAction(btn.action, item)}
        >
          {btn.label}
        </Button>
      ))}
    </div>
  )
}

interface Column {
  key: string
  label: string
  render?: (item: any) => React.ReactNode
  className?: string
  cellClassName?: string
}

function getColumnsForType(resourceType: string): Column[] {
  switch (resourceType) {
    case 'deployments':
    case 'statefulsets':
    case 'rollouts':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        {
          key: 'replicas',
          label: '副本',
          render: (item) => item.replicas ?? '-',
        },
        {
          key: 'ready_replicas',
          label: '就绪',
          render: (item) => item.ready_replicas ?? '-',
        },
        { key: 'status', label: '状态', render: (item) => <Badge variant="secondary">{item.status || '-'}</Badge> },
        { key: 'age', label: '年龄' },
      ]

    case 'pods':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        {
          key: 'status',
          label: '状态',
          render: (item) => {
            const variant = item.status === 'Running' ? 'default' : item.status === 'Failed' ? 'destructive' : 'secondary'
            return <Badge variant={variant}>{item.status || '-'}</Badge>
          },
        },
        { key: 'ready', label: '就绪' },
        { key: 'restarts', label: '重启' },
        { key: 'age', label: '年龄' },
        { key: 'node', label: '节点', cellClassName: 'font-mono text-sm' },
      ]

    case 'services':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'type', label: '类型' },
        { key: 'cluster_ip', label: 'Cluster IP', cellClassName: 'font-mono' },
        {
          key: 'ports',
          label: '端口',
          render: (item) => Array.isArray(item.ports) ? item.ports.join(', ') : (item.ports || '-'),
        },
        { key: 'age', label: '年龄' },
      ]

    case 'ingresses':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'hosts', label: 'Hosts' },
        { key: 'class_name', label: 'Class' },
        { key: 'tls', label: 'TLS' },
        { key: 'age', label: '年龄' },
      ]

    case 'hpas':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'min_replicas', label: '最小副本' },
        { key: 'max_replicas', label: '最大副本' },
        { key: 'current_replicas', label: '当前副本' },
        {
          key: 'cpu_percent',
          label: 'CPU',
          render: (item) => item.cpu_percent != null ? `${item.cpu_percent}%` : '-',
        },
        {
          key: 'memory_percent',
          label: '内存',
          render: (item) => item.memory_percent != null ? `${item.memory_percent}%` : '-',
        },
        { key: 'age', label: '年龄' },
      ]

    case 'helm':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'chart', label: 'Chart' },
        { key: 'app_version', label: 'App Version' },
        { key: 'revision', label: 'Revision' },
        { key: 'status', label: '状态' },
      ]

    case 'configmaps':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        {
          key: 'data_keys',
          label: 'Data Keys',
          render: (item) => (item.data_keys || []).join(', ') || '-',
        },
        { key: 'age', label: '年龄' },
      ]

    case 'secrets':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'type', label: '类型' },
        {
          key: 'data_keys',
          label: 'Data Keys',
          render: (item) => (item.data_keys || []).join(', ') || '-',
        },
        { key: 'age', label: '年龄' },
      ]

    case 'ingressroutes':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'hosts', label: 'Hosts' },
        { key: 'entry_points', label: 'EntryPoints' },
        { key: 'age', label: '年龄' },
      ]

    case 'ingressroutetcps':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'entry_points', label: 'EntryPoints' },
        { key: 'age', label: '年龄' },
      ]

    case 'ingressrouteudps':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'entry_points', label: 'EntryPoints' },
        { key: 'age', label: '年龄' },
      ]

    case 'apisixroutes':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'hosts', label: 'Hosts' },
        { key: 'age', label: '年龄' },
      ]

    case 'apisixtlses':
      return [
        { key: 'name', label: '名称', cellClassName: 'font-mono font-medium' },
        { key: 'namespace', label: '命名空间', cellClassName: 'font-mono text-sm' },
        { key: 'hosts', label: 'Hosts' },
        { key: 'secret', label: 'Secret' },
        { key: 'age', label: '年龄' },
      ]

    default:
      return [
        { key: 'name', label: '名称' },
        { key: 'namespace', label: '命名空间' },
      ]
  }
}

interface BatchToolbarProps {
  selectedCount: number
  onRestart: () => void
  onDelete: () => void
  onUpdateLabels: () => void
  onClear: () => void
}

function BatchToolbar({ selectedCount, onRestart, onDelete, onUpdateLabels, onClear }: BatchToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-md border">
      <span className="text-sm text-muted-foreground">
        已选择 <strong>{selectedCount}</strong> 个 Pod
      </span>
      <div className="flex items-center gap-1 ml-auto">
        <Button variant="outline" size="sm" onClick={onRestart}>
          <RotateCw className="h-4 w-4 mr-1" />
          重启
        </Button>
        <Button variant="destructive" size="sm" onClick={onDelete}>
          <Trash2 className="h-4 w-4 mr-1" />
          删除
        </Button>
        <Button variant="outline" size="sm" onClick={onUpdateLabels}>
          <Tags className="h-4 w-4 mr-1" />
          更新标签
        </Button>
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X className="h-4 w-4 mr-1" />
          清空
        </Button>
      </div>
    </div>
  )
}
