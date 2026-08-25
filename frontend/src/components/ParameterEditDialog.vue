<script setup>
import { computed, ref } from 'vue'
import { Plus, Delete, Close, Check, Rank } from '@element-plus/icons-vue'
import Draggable from 'vuedraggable'

const props = defineProps({
  modelValue: { type: Object, default: null },
  value: { type: [Array, Object], default: () => [] },
  sheetNames: { type: Array, default: () => [] },
  selectedSheets: { type: Array, default: () => [] },
  excludeSheets: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'save'])
const checkedSheets = ref([])
const orderItems = ref([])
const rows = ref([])

// 比对表单多选下拉的候选：扫描结果 ∪ 当前已选。
// 并集保证「换文件后未扫描到但已选中」的表单不会从列表消失（从而无法被取消）。
const sheetOptions = computed(() => [
  ...new Set([...props.sheetNames, ...checkedSheets.value]),
])

// dict 表格「表单」列的候选：扫描结果 ∪ 本行已填值（可能是手输的未来表单）
function sheetOptionsFor(row) {
  const current = String(row.sheet || '').trim()
  return current ? [...new Set([...props.sheetNames, current])] : [...props.sheetNames]
}

function toRows(value) {
  const result = []
  const global = Array.isArray(value?.global) ? value.global : []
  if (global.length) result.push({ sheet: '', items: global.join(', ') })
  for (const [sheet, items] of Object.entries(value?.perSheet || {})) {
    result.push({ sheet, items: Array.isArray(items) ? items.join(', ') : String(items) })
  }
  return result
}

function rowsToValue() {
  const global = []
  const perSheet = {}
  for (const row of rows.value) {
    const items = row.items
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (!items.length) continue
    const sheet = String(row.sheet || '').trim()
    if (sheet) perSheet[sheet] = items
    else global.push(...items)
  }
  return { global: [...new Set(global)], perSheet }
}

function openDialog() {
  const model = props.modelValue
  if (!model) return
  if (model.type === 'sheets') {
    checkedSheets.value = props.sheetNames.length
      ? [...props.selectedSheets]
      : [...(Array.isArray(props.value) ? props.value : [])]
  } else if (model.type === 'fields' || model.type === 'anchors') {
    rows.value = toRows(props.value)
  } else if (model.type === 'order') {
    const available = props.selectedSheets.length
      ? props.selectedSheets
      : Array.isArray(props.value)
        ? props.value
        : []
    const existing = Array.isArray(props.value) ? props.value : []
    orderItems.value = [
      ...existing.filter((name) => available.includes(name)),
      ...available.filter((name) => !existing.includes(name)),
    ].map((name) => ({ name }))
  }
}

function addRow() {
  rows.value = [...rows.value, { sheet: '', items: '' }]
}

function removeRow(index) {
  rows.value = rows.value.filter((_row, rowIndex) => rowIndex !== index)
}

function save() {
  const model = props.modelValue
  if (!model) return
  let value
  if (model.type === 'sheets') {
    if (!props.sheetNames.length) {
      value = { include: [...checkedSheets.value], exclude: [...props.excludeSheets] }
    } else {
      const selected = new Set(checkedSheets.value)
      const unscannedExcluded = props.excludeSheets.filter(
        (name) => !props.sheetNames.includes(name)
      )
      value = {
        include: [...checkedSheets.value],
        exclude: [
          ...new Set([
            ...props.sheetNames.filter((name) => !selected.has(name)),
            ...unscannedExcluded,
          ]),
        ],
      }
    }
  } else if (model.type === 'order') {
    value = orderItems.value.map((item) => item.name)
  } else {
    value = rowsToValue()
  }
  emit('save', value)
  emit('update:modelValue', null)
}
</script>

<template>
  <el-dialog
    :model-value="!!modelValue"
    :title="modelValue ? '编辑：' + modelValue.title : ''"
    width="560px"
    append-to-body
    @update:model-value="(value) => emit('update:modelValue', value ? modelValue : null)"
    @open="openDialog"
  >
    <div v-if="modelValue" class="edit-body">
      <template v-if="modelValue.type === 'sheets'">
        <div v-if="sheetNames.length" class="sheet-toolbar">
          <el-button size="small" text @click="checkedSheets = [...sheetNames]">全选</el-button>
          <el-button size="small" text @click="checkedSheets = []">清空</el-button>
        </div>
        <el-select
          v-model="checkedSheets"
          multiple
          filterable
          clearable
          collapse-tags
          collapse-tags-tooltip
          :max-collapse-tags="6"
          placeholder="搜索并选择要比对的表单"
          class="sheet-select"
        >
          <el-option v-for="name in sheetOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <div v-if="!sheetNames.length" class="edit-empty">
          请先上传旧版本或新版本文件，系统会自动扫描表单。
        </div>
        <div class="edit-hint">{{ modelValue.hint }}</div>
      </template>

      <template v-else-if="modelValue.type === 'order'">
        <div v-if="orderItems.length" class="order-list">
          <Draggable v-model="orderItems" item-key="name" handle=".drag-handle">
            <template #item="{ element }">
              <div class="order-row">
                <el-icon class="drag-handle" :size="16"><Rank /></el-icon>
                <span>{{ element.name }}</span>
              </div>
            </template>
          </Draggable>
        </div>
        <div v-else class="edit-empty">请先上传文件并选择需要比对的表单。</div>
        <div class="edit-hint">{{ modelValue.hint }}</div>
      </template>

      <template v-else-if="modelValue.type === 'fields' || modelValue.type === 'anchors'">
        <div class="dict-toolbar">
          <el-button size="small" :icon="Plus" title="添加行" aria-label="添加行" @click="addRow" />
        </div>
        <div class="dict-table">
          <div class="dict-row dict-header">
            <span>表单（可选）</span>
            <span>参数（逗号分隔）</span>
            <span></span>
          </div>
          <div v-for="(row, index) in rows" :key="index" class="dict-row">
            <el-select
              v-model="row.sheet"
              size="small"
              filterable
              clearable
              allow-create
              default-first-option
              placeholder="留空=全局；可输入后回车"
            >
              <el-option
                v-for="name in sheetOptionsFor(row)"
                :key="name"
                :label="name"
                :value="name"
              />
            </el-select>
            <el-input v-model="row.items" size="small" placeholder="字段1, 字段2" />
            <el-button
              size="small"
              type="danger"
              text
              :icon="Delete"
              title="删除此行"
              aria-label="删除此行"
              @click="removeRow(index)"
            />
          </div>
        </div>
        <div class="edit-hint">{{ modelValue.hint }}</div>
      </template>
    </div>

    <template #footer>
      <el-button :icon="Close" title="取消" aria-label="取消" @click="emit('update:modelValue', null)" />
      <el-button type="primary" :icon="Check" title="确定" aria-label="确定" @click="save" />
    </template>
  </el-dialog>
</template>

<style scoped>
.edit-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sheet-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dict-toolbar {
  display: flex;
}

/* el-select 默认宽度 100%，但 grid item 的 min-width 默认为 auto，长表单名会撑爆 1fr 轨道 */
.dict-row > .el-select,
.dict-row > .el-input {
  min-width: 0;
}

.sheet-select {
  width: 100%;
}

.sheet-toolbar {
  display: flex;
  gap: var(--space-sm);
}

.dict-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.dict-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr auto;
  gap: 8px;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid var(--color-border);
}

.dict-row:last-child {
  border-bottom: none;
}

.dict-header {
  background: var(--color-primary-subtle);
  color: var(--color-primary-dark);
  font-size: var(--font-sm);
  font-weight: 600;
}

.order-list {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.order-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.order-row:last-child {
  border-bottom: none;
}

.drag-handle {
  cursor: grab;
  color: var(--color-text-muted);
}

.edit-empty,
.edit-hint {
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}
</style>
