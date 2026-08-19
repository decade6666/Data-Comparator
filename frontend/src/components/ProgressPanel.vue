<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Number, default: 0 },
  message: { type: String, default: '准备就绪' },
  status: { type: String, default: 'idle' },
})

const statusText = computed(() => {
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
    <div class="panel-header">进度</div>
    <div class="panel-body">
      <div class="progress-label">
        <span>{{ message }}</span>
        <span class="progress-status">{{ statusText }} · {{ Math.round(progress) }}%</span>
      </div>
      <el-progress
        :percentage="Math.round(progress)"
        :stroke-width="14"
        striped
        :color="barColor"
      />
    </div>
  </div>
</template>
