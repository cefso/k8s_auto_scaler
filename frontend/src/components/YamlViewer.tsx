import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface YamlViewerProps {
  yaml: string
  showCollapseToggle?: boolean
  className?: string
}

// Reusable YAML field collapse logic (from Vue version)
function collapseYamlFields(yaml: string): string {
  const lines = yaml.split('\n')
  const result: string[] = []
  const fieldsToCollapse = ['managedFields', 'status']

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.trim() === '') {
      result.push(line)
      continue
    }

    const fieldMatch = line.match(/^(\s*)(\w+):\s*$/)
    if (fieldMatch) {
      const fieldIndent = fieldMatch[1].length
      const fieldName = fieldMatch[2]

      if (fieldsToCollapse.includes(fieldName)) {
        result.push(`${fieldMatch[1]}# --- ${fieldName} 已折叠 ---`)

        i++
        let contentIndent: number | null = null
        let isArray = false

        while (i < lines.length) {
          const currentLine = lines[i]

          if (currentLine.trim() === '') {
            i++
            continue
          }

          const currentIndent = currentLine.search(/\S/)

          if (contentIndent === null) {
            contentIndent = currentIndent
            isArray = currentLine.trim().startsWith('-')
          }

          if (isArray) {
            if (currentIndent <= contentIndent - 1) {
              break
            }
            if (currentIndent === contentIndent && !currentLine.trim().startsWith('-')) {
              break
            }
          } else {
            if (currentIndent <= fieldIndent) {
              break
            }
          }

          i++
        }
        continue
      }
    }

    result.push(line)
  }

  return result.join('\n')
}

export function YamlViewer({ yaml, showCollapseToggle = true, className }: YamlViewerProps) {
  const [showCollapsed, setShowCollapsed] = useState(true)

  const displayYaml = showCollapsed ? collapseYamlFields(yaml) : yaml

  return (
    <div className={cn('flex flex-col', className)}>
      {showCollapseToggle && (
        <div className="flex items-center gap-2 mb-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowCollapsed(!showCollapsed)}
          >
            {showCollapsed ? '显示全部字段' : '折叠冗余字段'}
          </Button>
        </div>
      )}
      <pre className="flex-1 overflow-auto p-4 bg-muted rounded-md font-mono text-sm">
        <code>{displayYaml}</code>
      </pre>
    </div>
  )
}

export default YamlViewer
