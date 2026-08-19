<script setup>
defineProps({
  running: { type: Boolean, default: false },
  finished: { type: Boolean, default: false },
})

defineEmits(['start', 'stop', 'download', 'open-help', 'open-settings'])
</script>

<template>
  <div class="action-bar">
    <el-button
      v-if="!running"
      type="success"
      :disabled="finished"
      @click="$emit('start')"
    >
      ▶ 开始比对
    </el-button>
    <el-button v-else type="danger" @click="$emit('stop')">■ 停止比对</el-button>
    <el-button v-if="finished" type="primary" @click="$emit('download')">
      下载报告
    </el-button>
    <el-button @click="$emit('open-help')">使用帮助</el-button>
    <el-button @click="$emit('open-settings')">高级设置</el-button>
  </div>
</template>
