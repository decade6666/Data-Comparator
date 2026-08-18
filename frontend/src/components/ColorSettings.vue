<script setup>
const props = defineProps({
  colors: { type: Object, required: true },
})

const emit = defineEmits(['update:colors'])

const ITEMS = [
  { key: 'highlight_fill', label: '更新高亮色' },
  { key: 'missing_sheet_tab', label: '删除标签色' },
  { key: 'new_sheet_tab', label: '新增标签色' },
]

function updateColor(key, value) {
  emit('update:colors', {
    ...props.colors,
    [key]: value,
  })
}
</script>

<template>
  <div class="panel">
    <div class="panel-header">颜色设置</div>
    <div class="panel-body color-row">
      <div v-for="item in ITEMS" :key="item.key" class="color-item">
        <span class="color-swatch" :style="{ background: colors[item.key] }"></span>
        <span class="color-label">{{ item.label }}</span>
        <el-color-picker
          :model-value="colors[item.key]"
          :predefine="['#FFE5E5', '#DC143C', '#00FF00']"
          @update:model-value="updateColor(item.key, $event)"
        />
        <code class="color-hex">{{ colors[item.key] }}</code>
      </div>
      <div class="color-hint">颜色作用于生成的 Excel 报告，不影响界面显示。</div>
    </div>
  </div>
</template>

<style scoped>
.color-label {
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}

.color-hex {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: var(--font-xs);
  color: var(--color-text-muted);
}

.color-hint {
  width: 100%;
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}
</style>
