<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { api } from '../composables/useApi'

const props = defineProps({
  modelValue: { type: Object, default: null }, // { key, title, type, hint }
  value: { type: [Array, Object], default: () => [] },
  oldFilePath: { type: String, default: '' },
  oldFileUploadId: { type: String, default: null },
  newFilePath: { type: String, default: '' },
  newFileUploadId: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue', 'save'])

const text = ref('')
const sheetNames = ref([])
const loadingSheets = ref(false)
const dictRows = ref([])

function textToValue() {
  return text.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function valueToText(value) {
  if (Array.isArray(value)) return value.join('\n')
  return ''
}

const isDict = computed(() => props.modelValue && props.modelValue.type === 'dict')
const isOrder = computed(() => props.modelValue && props.modelValue.type === 'order')

function toDictRows(value) {
  const rows = []
  for (const [sheet, items] of Object.entries(value || {})) {
    rows.push({ sheet, items: Array.isArray(items) ? items.join(', ') : String(items) })
  }
  return rows
}

function dictRowsToValue() {
  const result = {}
  for (const row of dictRows.value) {
    const key = row.sheet.trim()
    if (!key) continue
    result[key] = row.items
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return result
}

function openDialog() {
  const model = props.modelValue
  if (!model) return
  if (model.type === 'list' || model.type === 'sheetlist') {
    text.value = valueToText(props.value)
  } else if (model.type === 'dict') {
    dictRows.value = toDictRows(props.value)
  } else if (model.type === 'order') {
    dictRows.value = toDictRows(props.value)
  }
}

async function discoverSheets() {
  loadingSheets.value = true
  try {
    const filePath = props.oldFilePath || props.newFilePath
    const uploadId = props.oldFileUploadId || props.newFileUploadId
    if (!filePath && !uploadId) {
      ElMessage.warning('请先选择旧版本或新版本文件')
      return
    }
    const params = uploadId ? `upload_id=${uploadId}` : `file_path=${encodeURIComponent(filePath)}`
    const body = await api.get(`/sheets?${params}`)
    sheetNames.value = body.sheets
    ElMessage.success(`发现 ${body.sheets.length} 个表单`)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loadingSheets.value = false
  }
}

function toggleSheet(name) {
  const list = textToValue()
  const index = list.indexOf(name)
  if (index >= 0) list.splice(index, 1)
  else list.push(name)
  text.value = list.join('\n')
}

function addDictRow() {
  dictRows.value.push({ sheet: '', items: '' })
}

function removeDictRow(index) {
  dictRows.value.splice(index, 1)
}

function save() {
  const model = props.modelValue
  if (!model) return
  let value
  if (model.type === 'list' || model.type === 'sheetlist') {
    value = textToValue()
  } else if (model.type === 'dict') {
    value = dictRowsToValue()
  } else {
    value = textToValue()
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
    @update:model-value="(v) => emit('update:modelValue', v ? modelValue : null)"
    @open="openDialog"
  >
    <div v-if="modelValue" class="edit-body">
      <div v-if="modelValue.type === 'sheetlist'" class="discover-row">
        <el-button size="small" :icon="Refresh" :loading="loadingSheets" @click="discoverSheets">
          发现表单名称
        </el-button>
        <div v-if="sheetNames.length" class="sheet-checkboxes">
          <el-checkbox
            v-for="name in sheetNames"
            :key="name"
            :model-value="textToValue().includes(name)"
            @update:model-value="toggleSheet(name)"
          >
            {{ name }}
          </el-checkbox>
        </div>
      </div>

      <template v-if="modelValue.type === 'dict'">
        <div class="dict-toolbar">
          <el-button size="small" @click="addDictRow">添加行</el-button>
        </div>
        <div class="dict-table">
          <div class="dict-row dict-header">
            <span>表单名称</span>
            <span>字段（逗号分隔）</span>
            <span></span>
          </div>
          <div v-for="(row, index) in dictRows" :key="index" class="dict-row">
            <el-input v-model="row.sheet" size="small" placeholder="Sheet 名称" />
            <el-input v-model="row.items" size="small" placeholder="字段1, 字段2" />
            <el-button size="small" type="danger" text @click="removeDictRow(index)">
              删除
            </el-button>
          </div>
        </div>
        <div class="edit-hint">{{ modelValue.hint }}</div>
      </template>

      <template v-else>
        <el-input
          v-model="text"
          type="textarea"
          :rows="10"
          placeholder="每行一个值"
        />
        <div class="edit-hint">{{ modelValue.hint }}</div>
      </template>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', null)">取消</el-button>
      <el-button type="primary" @click="save">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.edit-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.discover-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sheet-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dict-toolbar {
  display: flex;
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

.edit-hint {
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}
</style>
