<script setup>
import { computed } from 'vue'
import { CircleClose, Document, Download, VideoPlay } from '@element-plus/icons-vue'

const props = defineProps({
  progress: { type: Number, default: 0 },
  message: { type: String, default: '准备就绪' },
  status: { type: String, default: 'idle' },
  hasLogs: { type: Boolean, default: false },
  scanning: { type: Boolean, default: false },
  scanProgress: { type: Number, default: 0 },
})

defineEmits(['start', 'stop', 'download-report', 'download-logs'])

const running = computed(() =>
  props.scanning || ['pending', 'running', 'cancelling'].includes(props.status)
)
const finished = computed(() => props.status === 'completed')

const displayProgress = computed(() => {
  if (props.scanning) return props.scanProgress
  if (props.status === 'idle') return props.scanProgress
  return props.progress
})

const statusText = computed(() => {
  if (props.scanning) return '扫描文件中…'
  const map = {
    idle: '准备就绪',
    pending: '等待中',
    running: '处理中',
    completed: '比对完成',
    failed: '比对失败',
    cancelled: '已停止',
    cancelling: '正在停止…',
  }
  return map[props.status] || '准备就绪'
})

const barColor = computed(() => {
  if (props.status === 'failed') return '#ef4444'
  if (props.status === 'cancelled') return '#f59e0b'
  if (props.status === 'completed') return '#22c55e'
  return undefined
})
</script>

<template>
  <div class="panel">
    <div class="panel-header">
      <span>进度</span>
      <div class="panel-header-actions">
        <el-button
          v-if="!running && !scanning"
          size="small"
          type="primary"
          plain
          :icon="VideoPlay"
          title="开始比对"
          aria-label="开始比对"
          @click="$emit('start')"
        />
        <el-button
          v-else-if="running && !scanning"
          size="small"
          type="danger"
          plain
          :icon="CircleClose"
          :disabled="props.status === 'cancelling'"
          title="停止比对"
          aria-label="停止比对"
          @click="$emit('stop')"
        />
        <el-button
          v-if="finished"
          size="small"
          type="success"
          plain
          :icon="Download"
          title="下载报告"
          aria-label="下载报告"
          @click="$emit('download-report')"
        />
        <el-button
          v-if="hasLogs"
          size="small"
          plain
          :icon="Document"
          title="下载日志"
          aria-label="下载日志"
          @click="$emit('download-logs')"
        />
      </div>
    </div>
    <div class="panel-body">
      <div class="progress-label">
        <span>{{ props.scanning ? `扫描文件中…` : message }}</span>
        <span class="progress-status">{{ statusText }} · {{ Math.round(displayProgress) }}%</span>
      </div>
      <el-progress
        :percentage="Math.round(displayProgress)"
        :stroke-width="14"
        striped
        :color="barColor"
      />
    </div>
  </div>
</template>
