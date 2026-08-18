<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PathSelector from './PathSelector.vue'
import StructureRow from './StructureRow.vue'
import ColorSettings from './ColorSettings.vue'
import ParameterCard from './ParameterCard.vue'
import ParameterEditDialog from './ParameterEditDialog.vue'

const props = defineProps({
  config: { type: Object, required: true },
})

const emit = defineEmits(['config-changed'])

const editing = ref(null)

const CARDS = [
  { key: 'common_cols', title: '排除字段', type: 'list', hint: '读取时直接丢弃的列' },
  { key: 'exclude_sheets', title: '排除表单', type: 'sheetlist', hint: '在指定表单之后生效' },
  { key: 'include_sheets', title: '指定表单', type: 'sheetlist', hint: '留空表示全部表单' },
  { key: 'ignore_cols', title: '忽略比对字段', type: 'list', hint: '字段仍输出，差异不计入' },
  { key: 'default_keys', title: '默认锚点', type: 'list', hint: '用于匹配新旧行的关键列' },
  { key: 'sheet_key_map', title: '自定义锚点', type: 'dict', hint: '按表单替换默认锚点' },
  { key: 'sheet_ignore_cols', title: '表单忽略字段', type: 'dict', hint: '按表单替换全局忽略字段' },
  { key: 'sheet_order', title: '表单顺序', type: 'order', hint: '拖拽调整输出顺序' },
]

watch(
  () => props.config,
  () => emit('config-changed'),
  { deep: true }
)

function patch(key, value) {
  emit('update:config', { ...props.config, [key]: value })
}
</script>

<template>
  <div class="panel">
    <div class="panel-header">路径选择</div>
    <div class="panel-body">
      <PathSelector
        label="旧版本文件"
        :model-value="config.old_file_path"
        :upload-id="config.old_file_upload_id"
        @update:model-value="patch('old_file_path', $event)"
        @update:upload-id="patch('old_file_upload_id', $event)"
      />
      <PathSelector
        label="新版本文件"
        :model-value="config.new_file_path"
        :upload-id="config.new_file_upload_id"
        @update:model-value="patch('new_file_path', $event)"
        @update:upload-id="patch('new_file_upload_id', $event)"
      />
      <PathSelector
        label="输出目录"
        :model-value="config.output_directory"
        :allow-upload="false"
        browse-type="directories"
        @update:model-value="patch('output_directory', $event)"
      />
    </div>
  </div>

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

  <div class="panel">
    <div class="panel-header">比对参数</div>
    <div class="panel-body">
      <ParameterCard
        v-for="card in CARDS"
        :key="card.key"
        :title="card.title"
        :hint="card.hint"
        :type="card.type"
        :value="config[card.key]"
        @edit="editing = card"
      />
    </div>
  </div>

  <ParameterEditDialog
    v-model="editing"
    :value="editing ? config[editing.key] : []"
    :old-file-path="config.old_file_path"
    :old-file-upload-id="config.old_file_upload_id"
    :new-file-path="config.new_file_path"
    :new-file-upload-id="config.new_file_upload_id"
    @save="(value) => { if (editing) { patch(editing.key, value); } }"
  />
</template>
