<script setup>
const props = defineProps({
  colors: { type: Object, required: true },
})

const emit = defineEmits(['update:colors'])

const ITEMS = [
  { key: 'highlight_fill', label: '更新' },
  { key: 'missing_sheet_tab', label: '删除' },
  { key: 'new_sheet_tab', label: '新增' },
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
      <template v-for="(item, index) in ITEMS" :key="item.key">
        <div v-if="index > 0" class="color-divider" />
        <div class="color-item">
          <span class="color-label">{{ item.label }}</span>
          <el-color-picker
            :model-value="colors[item.key]"
            :predefine="['#FFE5E5', '#DC143C', '#00FF00']"
            @update:model-value="updateColor(item.key, $event)"
          />
          <code class="color-hex">{{ colors[item.key] }}</code>
        </div>
      </template>
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

.color-divider {
  width: 1px;
  height: 24px;
  background: var(--color-border);
  flex-shrink: 0;
}
</style>
