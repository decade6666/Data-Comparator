<script setup>
defineProps({
  anchorRowNum: { type: Number, default: 1 },
  headerRowNum: { type: Number, default: 1 },
  mergeDeletedData: { type: Boolean, default: true },
})

const emit = defineEmits([
  'update:anchorRowNum',
  'update:headerRowNum',
  'update:mergeDeletedData',
])
</script>

<template>
  <div class="panel">
    <div class="panel-header">结构设置</div>
    <div class="panel-body structure-row">
      <span class="structure-item">
        锚点行号
        <el-input-number
          :model-value="anchorRowNum"
          :min="1"
          :max="99"
          size="small"
          @update:model-value="emit('update:anchorRowNum', $event)"
        />
      </span>
      <span class="structure-item">
        表头行号
        <el-input-number
          :model-value="headerRowNum"
          :min="1"
          :max="99"
          size="small"
          @update:model-value="emit('update:headerRowNum', $event)"
        />
      </span>
      <el-checkbox
        :model-value="mergeDeletedData"
        @update:model-value="emit('update:mergeDeletedData', $event)"
      >
        合并删除数据
      </el-checkbox>
    </div>
  </div>
</template>

<style scoped>
.structure-row {
  display: flex;
  align-items: center;
  gap: var(--space-xl);
  flex-wrap: wrap;
}

.structure-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}
</style>
