<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Moon, Sunny, Setting, QuestionFilled } from '@element-plus/icons-vue'
import { useTheme } from './composables/useTheme'
import { useSidebarResize } from './composables/useSidebarResize'
import { useJob } from './composables/useJob'
import { config, buildParameters, DEFAULT_WORKERS } from './composables/useConfig'
import AdvancedSettingsDialog from './components/AdvancedSettingsDialog.vue'
import ActionBar from './components/ActionBar.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import LogConsole from './components/LogConsole.vue'
import ConfigSidebar from './components/ConfigSidebar.vue'
import CompareForm from './components/CompareForm.vue'

const { isDark, toggleTheme } = useTheme()
const { sidebarWidth, resizerStyle, startResize } = useSidebarResize()
const job = useJob()

const helpVisible = ref(false)
const settingsVisible = ref(false)
const maxWorkers = ref(DEFAULT_WORKERS)

const running = computed(() => ['pending', 'running', 'cancelling'].includes(job.status.value))
const finished = computed(() => job.status.value === 'completed')

async function startCompare() {
  try {
    await job.submit(buildParameters())
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function stopCompare() {
  try {
    await job.cancel()
  } catch (err) {
    ElMessage.warning(err.message)
  }
}

function downloadReport() {
  job.download()
}

function updateConfig(patch) {
  Object.assign(config, patch)
}

function applyMaxWorkers(value) {
  config.max_workers = value
}
</script>

<template>
  <header class="app-header">
    <h1>数据集比对工具</h1>
    <div class="header-actions">
      <ActionBar
        :running="running"
        :finished="finished"
        @start="startCompare"
        @stop="stopCompare"
        @download="downloadReport"
        @open-help="helpVisible = true"
        @open-settings="settingsVisible = true"
      />
      <button
        class="icon-btn"
        title="切换深色模式"
        aria-label="切换深色模式"
        @click="toggleTheme"
      >
        <el-icon :size="16">
          <Sunny v-if="isDark" />
          <Moon v-else />
        </el-icon>
      </button>
      <button
        class="icon-btn"
        title="使用帮助"
        aria-label="使用帮助"
        @click="helpVisible = true"
      >
        <el-icon :size="16"><QuestionFilled /></el-icon>
      </button>
      <button
        class="icon-btn"
        title="高级设置"
        aria-label="高级设置"
        @click="settingsVisible = true"
      >
        <el-icon :size="16"><Setting /></el-icon>
      </button>
    </div>
  </header>

  <div class="app-main">
    <aside class="app-sidebar" :style="{ width: sidebarWidth + 'px' }">
      <ConfigSidebar />
    </aside>
    <div class="sidebar-resizer" :style="resizerStyle" @mousedown="startResize"></div>
    <main class="app-content">
      <ProgressPanel
        :progress="job.progress.value"
        :message="job.progressMessage.value"
        :status="job.status.value"
      />
      <CompareForm
        :config="config"
        @update:config="updateConfig"
        @config-changed="() => {}"
      />
      <LogConsole :lines="job.logLines.value" />
    </main>
  </div>

  <el-dialog v-model="helpVisible" title="使用帮助" width="720px" append-to-body>
    <div class="help-body">
      <h4>数据比对流程</h4>
      <ol>
        <li>选择旧版本文件与新版本文件（可上传，也可填写服务器路径）。</li>
        <li>指定输出目录，或留空使用默认临时目录。</li>
        <li>按需调整锚点行、表头行、颜色与各类比对参数。</li>
        <li>点击「开始比对」，观察进度与日志；可随时「停止比对」。</li>
        <li>完成后点击「下载报告」获取 Excel 比对结果。</li>
      </ol>
      <h4>参数说明</h4>
      <ul>
        <li><b>排除字段</b>：读取时直接丢弃的列。</li>
        <li><b>指定表单</b>：仅比对列出的 Sheet（留空表示全部）。</li>
        <li><b>忽略比对字段</b>：字段仍会输出，但差异不计入高亮与汇总。</li>
        <li><b>默认锚点 / 自定义锚点</b>：用于匹配新旧行的关键列，自定义锚点会整体替换默认锚点。</li>
      </ul>
    </div>
  </el-dialog>

  <AdvancedSettingsDialog
    v-model="settingsVisible"
    :max-workers="maxWorkers"
    :is-dark="isDark"
    @update:max-workers="applyMaxWorkers"
    @update:is-dark="toggleTheme"
  />
</template>

<style scoped>
.help-body h4 {
  color: var(--color-primary-dark);
  margin: 12px 0 6px;
}

.help-body h4:first-child {
  margin-top: 0;
}

.help-body li {
  margin-bottom: 4px;
}
</style>
