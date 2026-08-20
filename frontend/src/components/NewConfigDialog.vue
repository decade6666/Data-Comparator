<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../composables/useApi'
import { applyDocument } from '../composables/useConfig'
import {
  builtinTemplates,
  cancelEditConfigDialog,
  cancelNewConfigDialog,
  editConfigName,
  editConfigVisible,
  newConfigVisible,
  resolveEditConfigDialog,
  resolveNewConfigDialog,
} from '../composables/useConfigState'

const name = ref('')
const loadingTemplate = ref(false)

const visible = computed(() => newConfigVisible.value || editConfigVisible.value)
const isEdit = computed(() => editConfigVisible.value)

watch(visible, (open) => {
  if (open) name.value = isEdit.value ? editConfigName.value : ''
})

function templateLabel(templateName) {
  return templateName.replace(/^【模板】/, '')
}

async function importTemplate(templateName) {
  loadingTemplate.value = true
  try {
    const document = await api.get(`/configs/${encodeURIComponent(templateName)}`)
    applyDocument(document, { preserveFiles: true })
    ElMessage.success(`已导入模板：${templateLabel(templateName)}`)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loadingTemplate.value = false
  }
}

function confirm() {
  const trimmedName = name.value.trim()
  if (!trimmedName) {
    ElMessage.warning('项目名称不能为空')
    return
  }
  if (isEdit.value) resolveEditConfigDialog(trimmedName)
  else resolveNewConfigDialog(trimmedName)
}

function cancel() {
  if (isEdit.value) cancelEditConfigDialog()
  else cancelNewConfigDialog()
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑项目' : '新建项目'"
    width="440px"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="(v) => !v && cancel()"
  >
    <el-form label-position="top" @submit.prevent="confirm">
      <el-form-item label="项目名称">
        <el-input
          v-model="name"
          autofocus
          placeholder="请输入新项目名称"
          @keyup.enter="confirm"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="new-config-footer">
        <el-dropdown
          trigger="click"
          :disabled="loadingTemplate || !builtinTemplates.length"
          @command="importTemplate"
        >
          <el-button :loading="loadingTemplate">导入模板</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="templateName in builtinTemplates"
                :key="templateName"
                :command="templateName"
              >
                {{ templateLabel(templateName) }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div class="new-config-footer-actions">
          <el-button @click="cancel">取消</el-button>
          <el-button type="primary" @click="confirm">{{ isEdit ? '保存' : '创建' }}</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.new-config-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.new-config-footer-actions {
  display: flex;
  gap: var(--space-sm);
}

.new-config-footer-actions .el-button + .el-button {
  margin-left: 0;
}
</style>
