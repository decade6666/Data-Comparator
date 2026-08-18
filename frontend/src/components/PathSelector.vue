<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, FolderOpened } from '@element-plus/icons-vue'
import { api } from '../composables/useApi'
import BrowseDialog from './BrowseDialog.vue'

const props = defineProps({
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  uploadId: { type: String, default: null },
  allowUpload: { type: Boolean, default: true },
  browseType: { type: String, default: 'all' },
})

const emit = defineEmits(['update:modelValue', 'update:uploadId', 'uploaded'])

const browseVisible = ref(false)
const uploadRef = ref(null)

function chooseFromBrowser(path) {
  emit('update:modelValue', path)
  emit('update:uploadId', null)
}

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
</script>

<template>
  <div class="path-row">
    <span class="path-label">{{ label }}</span>
    <el-input
      :model-value="modelValue"
      placeholder="填写服务器路径，或上传文件"
      clearable
      @update:model-value="emit('update:modelValue', $event)"
    />
    <el-button :icon="FolderOpened" @click="browseVisible = true">浏览</el-button>
    <el-upload
      v-if="allowUpload"
      ref="uploadRef"
      :show-file-list="false"
      :before-upload="handleUpload"
      accept=".xlsx,.xls"
    >
      <el-button :icon="UploadFilled">上传</el-button>
    </el-upload>
  </div>

  <BrowseDialog
    v-model="browseVisible"
    :browse-type="browseType"
    @select="chooseFromBrowser"
  />
</template>

<style scoped>
.path-label {
  flex-shrink: 0;
  width: 100px;
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}
</style>
