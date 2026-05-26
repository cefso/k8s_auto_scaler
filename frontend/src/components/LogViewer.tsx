import { useState, useEffect, useRef, useCallback } from 'react'
import { logsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2, Download, Trash2, Pause, Play } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

interface LogViewerProps {
  clusterId: number
  namespace: string
  podName: string
  initialContainer?: string
  onClose?: () => void
}

interface LogLine {
  content: string
  timestamp?: string
}

// 移除 ANSI 颜色转义序列
function stripAnsi(str: string): string {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
}

export function LogViewer({ clusterId, namespace, podName, initialContainer }: LogViewerProps) {
  const [logs, setLogs] = useState<LogLine[]>([])
  const [isPaused, setIsPaused] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [containers, setContainers] = useState<{ name: string; image: string }[]>([])
  const [selectedContainer, setSelectedContainer] = useState(initialContainer || '')
  const [isLoading, setIsLoading] = useState(true)
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch containers
  useEffect(() => {
    logsApi.getPodContainers(clusterId, namespace, podName)
      .then(res => {
        setContainers(res.data.containers || [])
        if (!selectedContainer && res.data.containers?.length > 0) {
          setSelectedContainer(res.data.containers[0].name)
        }
      })
      .catch(console.error)
  }, [clusterId, namespace, podName])

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    const token = useAuthStore.getState().token
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const params = new URLSearchParams({
      namespace,
      pod_name: podName,
      container: selectedContainer,
    })
    if (token) params.set('access_token', token)
    const wsUrl = `${protocol}//${window.location.host}/api/logs/ws/${clusterId}/pod?${params.toString()}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setIsConnected(true)
      setIsLoading(false)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'log') {
          setLogs(prev => [...prev.slice(-9999), { content: stripAnsi(data.content) }])
        } else if (data.type === 'done') {
          setIsLoading(false)
        }
      } catch {
        setLogs(prev => [...prev.slice(-9999), { content: stripAnsi(event.data) }])
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      // Auto reconnect if not intentionally closed
      if (!wsRef.current?.CLOSED) {
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000)
      }
    }

    ws.onerror = () => {
      setIsConnected(false)
    }

    wsRef.current = ws

    return ws
  }, [clusterId, namespace, podName, selectedContainer])

  useEffect(() => {
    if (!selectedContainer) return

    setIsLoading(true)
    setLogs([])

    const ws = connectWebSocket()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      ws.close()
    }
  }, [connectWebSocket, selectedContainer])

  // Auto scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const handleDownload = () => {
    const content = filteredLogs.map(l => l.content).join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${podName}-${selectedContainer}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClear = () => {
    setLogs([])
  }

  const filteredLogs = searchKeyword
    ? logs.filter(l => l.content.includes(searchKeyword))
    : logs

  return (
    <div className="flex flex-col bg-card rounded-lg border" style={{ maxHeight: 'calc(80vh - 120px)' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b p-3 bg-muted/50 shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium">{namespace}/{podName}</span>
          {containers.length > 1 && (
            <Select value={selectedContainer} onValueChange={setSelectedContainer}>
              <SelectTrigger className="w-36 h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {containers.map(c => (
                  <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <Checkbox
              id="auto-scroll"
              checked={autoScroll}
              onCheckedChange={(checked) => setAutoScroll(!!checked)}
            />
            <Label htmlFor="auto-scroll" className="text-sm cursor-pointer">自动滚动</Label>
          </div>
          <Input
            placeholder="搜索"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            className="w-32 h-8"
          />
          <Button size="sm" variant="outline" onClick={handleDownload}>
            <Download className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" onClick={handleClear}>
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant={isPaused ? 'default' : 'outline'}
            onClick={() => setIsPaused(!isPaused)}
          >
            {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            {isPaused ? '继续' : '暂停'}
          </Button>
        </div>
      </div>

      {/* Log Content */}
      <div ref={scrollRef} className="flex-1 overflow-auto font-mono text-sm p-4 bg-background" style={{ maxHeight: 'calc(80vh - 180px)' }}>
        {isLoading && logs.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            <span className="text-muted-foreground">加载中...</span>
          </div>
        )}
        {filteredLogs.map((log, i) => (
          <div
            key={i}
            className={cn(
              'py-0.5 whitespace-pre-wrap break-all',
              searchKeyword && log.content.includes(searchKeyword) && 'bg-yellow-500/20'
            )}
          >
            {log.content}
          </div>
        ))}
      </div>

      {/* Status Bar */}
      <div className="flex items-center gap-2 border-t px-4 py-2 text-xs text-muted-foreground shrink-0">
        <span>共 {logs.length} 行</span>
        {searchKeyword && <span>| 匹配 {filteredLogs.length} 行</span>}
        <span>|</span>
        <span className={cn('flex items-center gap-1', isConnected ? 'text-green-500' : 'text-muted')}>
          <span className="w-2 h-2 rounded-full bg-current" />
          {isConnected ? '已连接' : '未连接'}
        </span>
      </div>
    </div>
  )
}

export default LogViewer
