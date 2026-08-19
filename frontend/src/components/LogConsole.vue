<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  lines: { type: Array, default: () => [] },
})

const container = ref(null)

watch(
  () => props.lines.length,
  async () => {
    await nextTick()
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  }
)
</script>

<template>
  <div class="panel">
    <div class="panel-header">运行日志</div>
    <div class="panel-body">
      <div ref="container" class="log-console">
        <div v-if="!lines.length" class="log-line">暂无日志</div>
        <div v-for="(line, index) in lines" :key="index" class="log-line">
          {{ line }}
        </div>
      </div>
    </div>
  </div>
</template>
