import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'

interface BatchItem {
  namespace: string
  name: string
}

interface BatchConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  action: 'restart' | 'delete'
  items: BatchItem[]
  onConfirm: () => void
}

export function BatchConfirmDialog({ open, onOpenChange, action, items, onConfirm }: BatchConfirmDialogProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleConfirm = async () => {
    setIsLoading(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } finally {
      setIsLoading(false)
    }
  }

  const actionText = action === 'restart' ? '重启' : '删除'
  const actionColor = action === 'restart' ? 'default' : 'destructive'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认批量{actionText}</DialogTitle>
          <DialogDescription>
            即将对以下 {items.length} 个 Pod 执行{actionText}操作
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-[200px] rounded-md border p-2">
          <div className="space-y-1">
            {items.map((item, index) => (
              <div key={`${item.namespace}-${item.name}-${index}`} className="text-sm font-mono py-1">
                <span className="text-muted-foreground">{item.namespace}/</span>
                <span>{item.name}</span>
              </div>
            ))}
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button variant={actionColor} onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? '处理中...' : `确认${actionText}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface UpdateLabelsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  items: BatchItem[]
  onConfirm: (labels: Record<string, string>) => void
}

export function UpdateLabelsDialog({ open, onOpenChange, items, onConfirm }: UpdateLabelsDialogProps) {
  const [labelsInput, setLabelsInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleConfirm = async () => {
    const labels: Record<string, string> = {}
    const lines = labelsInput.trim().split('\n')

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const eqIndex = trimmed.indexOf('=')
      if (eqIndex === -1) {
        // 认为是 key=true 的格式
        labels[trimmed] = 'true'
      } else {
        const key = trimmed.slice(0, eqIndex).trim()
        const value = trimmed.slice(eqIndex + 1).trim()
        if (key) labels[key] = value
      }
    }

    if (Object.keys(labels).length === 0) return

    setIsLoading(true)
    try {
      await onConfirm(labels)
      onOpenChange(false)
      setLabelsInput('')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>批量更新标签</DialogTitle>
          <DialogDescription>
            将为以下 {items.length} 个 Pod 更新标签
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-[120px] rounded-md border p-2 mb-4">
          <div className="space-y-1">
            {items.map((item, index) => (
              <div key={`${item.namespace}-${item.name}-${index}`} className="text-sm font-mono py-1">
                <span className="text-muted-foreground">{item.namespace}/</span>
                <span>{item.name}</span>
              </div>
            ))}
          </div>
        </ScrollArea>
        <div className="space-y-2">
          <Label htmlFor="labels-input">标签（格式：key=value，每行一个）</Label>
          <Input
            id="labels-input"
            placeholder="app=v2&#10;version=stable"
            value={labelsInput}
            onChange={(e) => setLabelsInput(e.target.value)}
            className="font-mono"
          />
          <p className="text-xs text-muted-foreground">
            示例：输入 <code className="bg-muted px-1">app=v2</code> 会将标签 app 设置为 v2
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleConfirm} disabled={isLoading || !labelsInput.trim()}>
            {isLoading ? '处理中...' : '确认更新'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
