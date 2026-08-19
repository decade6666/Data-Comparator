<script setup>
import { ElMessage } from 'element-plus'
import { UploadFilled, Close } from '@element-plus/icons-vue'
import { api } from '../composables/useApi'

const props = defineProps({
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  uploadId: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue', 'update:uploadId', 'uploaded'])

async function handleUpload(file) {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const body = await api.postForm('/upload', formData)
    emit('update:uploadId', body.upload_id)
    emit('update:modelValue', body.filename)
    emit('uploaded', { uploadId: body.upload_id, filename: body.filename })
    ElMessage.success(`已上传 ${body.filename}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
  return false
}

function clear() {
  emit('update:modelValue', '')
  emit('update:uploadId', null)
}
</script>

<template>
  <div class="file-selector">
    <span class="file-label">{{ label }}</span>
    <el-upload
      :show-file-list="false"
      :before-upload="handleUpload"
      accept=".xlsx,.xls"
    >
      <el-button
        size="small"
        :icon="UploadFilled"
        title="上传文件"
        aria-label="上传文件"
      />
    </el-upload>
    <span v-if="modelValue" class="file-name" :title="modelValue">{{ modelValue }}</span>
    <span v-else class="file-name file-name-empty">未选择文件</span>
    <el-button
      v-if="modelValue"
      :icon="Close"
      size="small"
      text
      title="清除文件"
      aria-label="清除文件"
      @click="clear"
    />
  </div>
</template>

<style scoped>
.file-selector {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex: 1;
  min-width: 0;
}

.file-label {
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}

.file-name {
  flex: 1;
  /* 覆盖 flex item 默认 min-width:auto，否则 text-overflow 不生效 */
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-sm);
}

.file-name-empty {
  color: var(--color-text-muted);
}
</style>
