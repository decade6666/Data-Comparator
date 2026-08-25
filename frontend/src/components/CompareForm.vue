<script setup>
import { computed, ref, watch } from 'vue'
import { useSheets } from '../composables/useSheets'
import { parameterDescription } from '../constants/parameterDescriptions'
import PathSelector from './PathSelector.vue'
import StructureRow from './StructureRow.vue'
import ColorSettings from './ColorSettings.vue'
import ParameterCard from './ParameterCard.vue'
import ParameterEditDialog from './ParameterEditDialog.vue'

const props = defineProps({
  config: { type: Object, required: true },
})

const emit = defineEmits(['config-changed', 'update:config'])
const editing = ref(null)
const { allSheets, scanFile, resetSheets } = useSheets()

const CARDS = [
  {
    key: 'common_cols',
    title: '排除字段',
    type: 'fields',
    globalKey: 'common_cols',
    perSheetKey: 'sheet_common_cols',
    hint: '单参数为全局排除字段，双参数为指定表单排除字段（整体替换全局）',
  },
  { key: 'sheet_scope', title: '比对表单', type: 'sheets', hint: '只需勾选要比对的扫描结果' },
  {
    key: 'ignore_settings',
    title: '忽略字段',
    type: 'fields',
    globalKey: 'ignore_cols',
    perSheetKey: 'sheet_ignore_cols',
    hint: '单参数为全局字段，双参数为指定表单字段',
  },
  {
    key: 'anchor_settings',
    title: '锚点',
    type: 'anchors',
    globalKey: 'default_keys',
    perSheetKey: 'sheet_key_map',
    hint: '单参数为默认锚点，双参数为指定表单锚点',
  },
  { key: 'sheet_order', title: '表单顺序', type: 'order', hint: '拖拽调整输出顺序' },
]

const selectedSheets = computed(() => {
  if (!allSheets.value.length) return [...(props.config.sheet_order || [])]
  const included = new Set(props.config.include_sheets || [])
  if (included.size) return allSheets.value.filter((name) => included.has(name))
  const excluded = new Set(props.config.exclude_sheets || [])
  return allSheets.value.filter((name) => !excluded.has(name))
})

function cardValue(card) {
  if (card.type === 'sheets') return selectedSheets.value
  if (card.globalKey) {
    return {
      global: props.config[card.globalKey] || [],
      perSheet: props.config[card.perSheetKey] || {},
    }
  }
  return props.config[card.key]
}

function patch(key, value) {
  emit('update:config', { [key]: value })
}

function handleUpload({ uploadId }, kind) {
  scanFile(uploadId, kind)
}

function handleClear(kind) {
  resetSheets(kind)
}

function saveEditedValue(value) {
  const card = editing.value
  if (!card) return
  if (card.type === 'sheets') {
    patch('include_sheets', value.include)
    patch('exclude_sheets', value.exclude)
  } else if (card.globalKey) {
    patch(card.globalKey, value.global)
    patch(card.perSheetKey, value.perSheet)
  } else {
    patch(card.key, value)
  }
}

watch(
  () => props.config,
  () => emit('config-changed'),
  { deep: true }
)
</script>

<template>
  <div class="panel">
    <div class="panel-header">比对文件</div>
    <div class="panel-body file-row">
      <PathSelector
        label="旧版本"
        :model-value="config.old_file_path"
        :upload-id="config.old_file_upload_id"
        @update:model-value="patch('old_file_path', $event)"
        @update:upload-id="patch('old_file_upload_id', $event)"
        @uploaded="handleUpload($event, 'old')"
        @cleared="handleClear('old')"
      />
      <PathSelector
        label="新版本"
        :model-value="config.new_file_path"
        :upload-id="config.new_file_upload_id"
        @update:model-value="patch('new_file_path', $event)"
        @update:upload-id="patch('new_file_upload_id', $event)"
        @uploaded="handleUpload($event, 'new')"
        @cleared="handleClear('new')"
      />
    </div>
  </div>

  <div class="structure-color-row">
    <StructureRow
      :anchor-row-num="config.anchor_row_num"
      :header-row-num="config.header_row_num"
      :merge-deleted-data="config.merge_deleted_data"
      @update:anchor-row-num="patch('anchor_row_num', $event)"
      @update:header-row-num="patch('header_row_num', $event)"
      @update:merge-deleted-data="patch('merge_deleted_data', $event)"
    />

    <ColorSettings
      :colors="config.colors"
      @update:colors="patch('colors', $event)"
    />
  </div>

  <div class="panel">
    <div class="panel-header">比对参数</div>
    <div class="panel-body">
      <ParameterCard
        v-for="card in CARDS"
        :key="card.key"
        :title="card.title"
        :type="card.type"
        :value="cardValue(card)"
        :description="parameterDescription(card.key)"
        @edit="editing = card"
      />
    </div>
  </div>

  <ParameterEditDialog
    v-model="editing"
    :value="editing ? cardValue(editing) : []"
    :sheet-names="allSheets"
    :selected-sheets="selectedSheets"
    :exclude-sheets="config.exclude_sheets"
    @save="saveEditedValue"
  />
</template>
