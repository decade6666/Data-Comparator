<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Delete,
  CopyDocument,
  EditPen,
  Upload,
  Download,
} from '@element-plus/icons-vue'
import { api } from '../composables/useApi'
import {
  builtinTemplates,
  clearSelectedConfig,
  currentName,
  openEditConfigDialog,
  openNewConfigDialog,
  restoreLastConfig,
  saveConfig,
  selectConfig,
} from '../composables/useConfigState'
import {
  listConfigs,
  deleteConfig,
  copyConfig,
  renameConfig,
} from '../composables/useConfig'

const configs = ref([])
const userConfigs = computed(() =>
  configs.value.filter((name) => !builtinTemplates.value.includes(name))
)

async function refresh() {
  const body = await listConfigs()
  configs.value = body.configs
  builtinTemplates.value = body.builtin_templates
}

async function select(name) {
  try {
    await selectConfig(name)
    ElMessage.success(`已加载项目：${name}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function createNew() {
  const name = await openNewConfigDialog()
  if (!name) return
  try {
    await saveConfig(name)
    await refresh()
    ElMessage.success(`已创建：${name}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function removeConfig(name) {
  if (!name) return
  if (builtinTemplates.value.includes(name)) {
    ElMessage.warning('内置模板不能删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除项目「${name}」吗？`,
      '删除项目',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteConfig(name)
    if (currentName.value === name) clearSelectedConfig()
    await refresh()
    ElMessage.success('已移至回收站')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function editConfig(name) {
  try {
    await selectConfig(name)
    const newName = await openEditConfigDialog(name)
    if (!newName) return
    const renamed = newName !== name
    if (renamed) await renameConfig(name, newName)
    await saveConfig(newName)
    await refresh()
    await selectConfig(newName)
    ElMessage.success(renamed ? `已重命名项目：${newName}` : `已保存：${newName}`)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function duplicateConfig(name) {
  if (!name) return
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入新项目名称',
      '复制项目',
      {
        confirmButtonText: '复制',
        cancelButtonText: '取消',
        inputValidator: (value) => (value && value.trim() ? true : '名称不能为空'),
      }
    )
    const newName = value.trim()
    await copyConfig(name, newName)
    await refresh()
    await selectConfig(newName)
    ElMessage.success('复制成功')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function exportCurrent() {
  if (!currentName.value) return
  try {
    await ElMessageBox.confirm(
      '导出的项目文件不包含已上传的比对文件，导入后需要重新上传。',
      '导出项目',
      { type: 'warning', confirmButtonText: '继续导出', cancelButtonText: '取消' }
    )
    await api.download(
      `/configs/${encodeURIComponent(currentName.value)}/export`,
      `${currentName.value}.json`
    )
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function importConfig(file) {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const body = await api.postForm('/configs/import', formData)
    ElMessage.success(`已导入：${body.name}`)
    await refresh()
  } catch (err) {
    ElMessage.error(err.message)
  }
  return false
}

watch(currentName, (name, previousName) => {
  if (!name || name === previousName) return
  refresh().catch((err) => ElMessage.error(err.message))
})

onMounted(async () => {
  try {
    await refresh()
    const restored = await restoreLastConfig(userConfigs.value)
    if (restored) ElMessage.success(`已恢复项目：${currentName.value}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
})
</script>

<template>
  <div>
    <div class="sidebar-title">项目管理</div>
    <div class="sidebar-actions">
      <el-button
        size="small"
        type="primary"
        plain
        :icon="Plus"
        title="新建项目"
        aria-label="新建项目"
        @click="createNew"
      />
      <el-upload
        :show-file-list="false"
        :before-upload="importConfig"
        accept=".json"
      >
        <el-button
          size="small"
          plain
          :icon="Upload"
          title="导入项目"
          aria-label="导入项目"
        />
      </el-upload>
      <el-button
        size="small"
        plain
        :icon="Download"
        title="导出当前项目"
        aria-label="导出当前项目"
        @click="exportCurrent"
      />
    </div>

    <div
      v-for="name in userConfigs"
      :key="name"
      class="config-item"
      :class="{ active: name === currentName }"
      :title="name"
      @click="select(name)"
    >
      <span class="config-item-name">{{ name }}</span>
      <span class="config-item-actions" @click.stop>
        <el-button
          size="small"
          text
          :icon="EditPen"
          title="编辑项目"
          :aria-label="`编辑项目：${name}`"
          @click.stop="editConfig(name)"
        />
        <el-button
          size="small"
          text
          :icon="CopyDocument"
          title="复制项目"
          :aria-label="`复制项目：${name}`"
          @click.stop="duplicateConfig(name)"
        />
        <el-button
          size="small"
          text
          type="danger"
          :icon="Delete"
          title="删除项目"
          :aria-label="`删除项目：${name}`"
          @click.stop="removeConfig(name)"
        />
      </span>
    </div>

    <div v-if="!userConfigs.length" class="empty-hint" style="padding: 0 16px">
      （暂无项目）
    </div>
  </div>
</template>
