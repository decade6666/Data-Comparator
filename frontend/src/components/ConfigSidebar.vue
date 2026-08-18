<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Delete,
  CopyDocument,
  Upload,
  Download,
} from '@element-plus/icons-vue'
import { api } from '../composables/useApi'
import {
  config,
  applyDocument,
  saveCurrentConfig,
  loadConfig,
  listConfigs,
  deleteConfig,
  copyConfig,
} from '../composables/useConfig'

const configs = ref([])
const builtinTemplates = ref([])
const currentName = ref('')

async function refresh() {
  const body = await listConfigs()
  configs.value = body.configs
  builtinTemplates.value = body.builtin_templates
}

function select(name) {
  loadConfig(name)
    .then(() => {
      currentName.value = name
      ElMessage.success(`已加载配置：${name}`)
    })
    .catch((err) => ElMessage.error(err.message))
}

async function saveCurrent() {
  if (!currentName.value) {
    ElMessage.warning('请先选择或新建一个配置')
    return
  }
  try {
    await saveCurrentConfig(currentName.value)
    ElMessage.success(`已保存：${currentName.value}`)
    await refresh()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function createNew() {
  try {
    const { value } = await ElMessageBox.prompt('请输入新配置名称', '新建配置', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '名称不能为空'),
    })
    const name = value.trim()
    await saveCurrentConfig(name)
    currentName.value = name
    await refresh()
    ElMessage.success(`已创建：${name}`)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function removeCurrent() {
  if (!currentName.value) return
  if (builtinTemplates.value.includes(currentName.value)) {
    ElMessage.warning('内置模板不能删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${currentName.value}」吗？`,
      '删除配置',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteConfig(currentName.value)
    currentName.value = ''
    await refresh()
    ElMessage.success('已删除')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function duplicateCurrent() {
  if (!currentName.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入新配置名称',
      '复制配置',
      {
        confirmButtonText: '复制',
        cancelButtonText: '取消',
        inputValidator: (v) => (v && v.trim() ? true : '名称不能为空'),
      }
    )
    await copyConfig(currentName.value, value.trim())
    await refresh()
    ElMessage.success('复制成功')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function exportCurrent() {
  if (!currentName.value) return
  window.open(
    api.apiUrl(`/configs/${encodeURIComponent(currentName.value)}/export`),
    '_blank'
  )
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

onMounted(() => {
  refresh().catch((err) => ElMessage.error(err.message))
})
</script>

<template>
  <div>
    <div class="sidebar-title">配置管理</div>
    <div class="sidebar-actions">
      <el-button size="small" type="primary" plain :icon="Plus" @click="createNew">
        新建
      </el-button>
      <el-button size="small" plain @click="saveCurrent">保存</el-button>
      <el-button size="small" plain :icon="Delete" @click="removeCurrent">
        删除
      </el-button>
      <el-button size="small" plain :icon="CopyDocument" @click="duplicateCurrent">
        复制
      </el-button>
      <el-upload
        :show-file-list="false"
        :before-upload="importConfig"
        accept=".json"
        style="display: inline-block"
      >
        <el-button size="small" plain :icon="Upload">导入</el-button>
      </el-upload>
      <el-button size="small" plain :icon="Download" @click="exportCurrent">
        导出
      </el-button>
    </div>

    <div class="sidebar-title" style="padding-top: 4px">我的配置</div>
    <div
      v-for="name in configs"
      :key="name"
      class="config-item"
      :class="{ active: name === currentName }"
      @click="select(name)"
    >
      {{ name }}
    </div>

    <div class="sidebar-title">内置模板</div>
    <div
      v-for="name in builtinTemplates"
      :key="name"
      class="config-item"
      :class="{ active: name === currentName }"
      @click="select(name)"
    >
      {{ name }}
    </div>

    <div v-if="!configs.length && !builtinTemplates.length" class="empty-hint" style="padding: 0 16px">
      （暂无配置）
    </div>
  </div>
</template>
