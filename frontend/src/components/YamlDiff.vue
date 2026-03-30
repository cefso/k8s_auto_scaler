<template>
  <div class="yaml-diff">
    <div class="diff-toolbar">
      <div class="diff-toolbar-left">
        <span class="diff-title">{{ title }}</span>
      </div>
      <div class="diff-toolbar-right">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">关闭</button>
      </div>
    </div>
    <div class="diff-content">
      <div class="diff-column">
        <div class="diff-column-header">原始 YAML</div>
        <pre class="yaml-original">{{ originalYaml }}</pre>
      </div>
      <div class="diff-column">
        <div class="diff-column-header">修改后 YAML</div>
        <pre class="yaml-modified">{{ modifiedYaml }}</pre>
      </div>
    </div>
    <div v-if="diffSummary.length > 0" class="diff-summary">
      <div class="diff-summary-title">差异摘要:</div>
      <ul>
        <li v-for="(line, index) in diffSummary" :key="index" :class="getDiffLineClass(line)">
          {{ line }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  originalYaml: string
  modifiedYaml: string
}>()

defineEmits<{
  close: []
}>()

const diffSummary = computed(() => {
  const originalLines = props.originalYaml.split('\n')
  const modifiedLines = props.modifiedYaml.split('\n')
  const summary: string[] = []

  const maxLines = Math.max(originalLines.length, modifiedLines.length)
  for (let i = 0; i < maxLines; i++) {
    const origLine = originalLines[i] || ''
    const modLine = modifiedLines[i] || ''
    if (origLine !== modLine) {
      if (!origLine) {
        summary.push(`+ 第 ${i + 1} 行: 添加 ${modLine.substring(0, 50)}${modLine.length > 50 ? '...' : ''}`)
      } else if (!modLine) {
        summary.push(`- 第 ${i + 1} 行: 删除 ${origLine.substring(0, 50)}${origLine.length > 50 ? '...' : ''}`)
      } else {
        summary.push(`~ 第 ${i + 1} 行: ${origLine.substring(0, 30)} → ${modLine.substring(0, 30)}${modLine.length > 30 ? '...' : ''}`)
      }
    }
  }

  return summary.slice(0, 20) // 最多显示 20 条
})

function getDiffLineClass(line: string): string {
  if (line.startsWith('+')) return 'diff-add'
  if (line.startsWith('-')) return 'diff-delete'
  return 'diff-change'
}
</script>

<style scoped>
.yaml-diff {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.diff-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: var(--bg-dark);
  border-bottom: 1px solid var(--border);
}

.diff-toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.diff-toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.diff-title {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--text-primary);
}

.diff-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.diff-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.diff-column:first-child {
  border-right: 1px solid var(--border);
}

.diff-column-header {
  padding: 0.5rem 1rem;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.yaml-original,
.yaml-modified {
  flex: 1;
  overflow: auto;
  padding: 1rem;
  margin: 0;
  background: var(--bg-dark);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-summary {
  padding: 0.75rem 1rem;
  background: var(--bg-hover);
  border-top: 1px solid var(--border);
  max-height: 150px;
  overflow-y: auto;
}

.diff-summary-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.diff-summary ul {
  margin: 0;
  padding-left: 1.25rem;
}

.diff-summary li {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  padding: 0.15rem 0;
}

.diff-add {
  color: var(--success);
}

.diff-delete {
  color: var(--error);
}

.diff-change {
  color: var(--warning);
}
</style>
