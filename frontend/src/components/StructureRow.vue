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
      <div class="merge-data-toggle">
        <span>删除数据</span>
        <el-switch
          :model-value="mergeDeletedData"
          inline-prompt
          active-text="保留"
          inactive-text="舍弃"
          :width="56"
          :aria-label="mergeDeletedData ? '删除数据：保留' : '删除数据：舍弃'"
          @update:model-value="emit('update:mergeDeletedData', $event)"
        />
      </div>
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

.structure-item,
.merge-data-toggle {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}

.structure-item,
.merge-data-toggle {
  gap: var(--space-sm);
}
</style>
