import { useQuery } from '@tanstack/react-query'
import { auditApi } from '@/api'
import { Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

export default function AuditLogPage() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => auditApi.getAuditLogs().then(res => res.data.items),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const getActionBadge = (action: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive'> = {
      create: 'default',
      update: 'secondary',
      delete: 'destructive',
      scale: 'default',
    }
    return (
      <Badge variant={variants[action] || 'secondary'}>
        {action}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">操作审计</h1>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>操作者</TableHead>
                <TableHead>操作类型</TableHead>
                <TableHead>资源类型</TableHead>
                <TableHead>资源名称</TableHead>
                <TableHead>命名空间</TableHead>
                <TableHead>详情</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    暂无审计日志
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log: any) => (
                  <TableRow key={log.id}>
                    <TableCell className="whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString('zh-CN')}
                    </TableCell>
                    <TableCell>{log.operator}</TableCell>
                    <TableCell>{getActionBadge(log.action)}</TableCell>
                    <TableCell>{log.resource_type}</TableCell>
                    <TableCell className="font-mono text-sm">{log.resource_name}</TableCell>
                    <TableCell className="font-mono text-sm">{log.namespace || '-'}</TableCell>
                    <TableCell className="text-muted-foreground max-w-xs truncate">
                      {log.details ? JSON.stringify(log.details) : '-'}
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
