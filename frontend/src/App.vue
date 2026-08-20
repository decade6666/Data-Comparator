<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Moon, Sunny, Setting, QuestionFilled, Lock, SwitchButton } from '@element-plus/icons-vue'
import { useTheme } from './composables/useTheme'
import { useSidebarResize } from './composables/useSidebarResize'
import { useJob } from './composables/useJob'
import { config, buildJobPayload } from './composables/useConfig'
import { autoSaveBeforeStart } from './composables/useConfigState'
import { useAuth } from './composables/useAuth'
import { useSheets } from './composables/useSheets'
import { PARAMETER_DESCRIPTIONS } from './constants/parameterDescriptions'
import AdvancedSettingsDialog from './components/AdvancedSettingsDialog.vue'
import NewConfigDialog from './components/NewConfigDialog.vue'
import UserAdminView from './components/UserAdminView.vue'
import LoginView from './components/LoginView.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import ConfigSidebar from './components/ConfigSidebar.vue'
import CompareForm from './components/CompareForm.vue'

const { isDark, toggleTheme } = useTheme()
const { sidebarWidth, resizerStyle, startResize } = useSidebarResize()
const job = useJob()
const auth = useAuth()
// 嵌套在对象里的 computed ref 在模板中不会自动解包（_unref(auth).isAuthenticated
// 拿到的是 ref 对象本身、恒为真），必须解构成顶层绑定后再用于模板。
const { isAuthenticated, isAdmin } = auth
const { scanning, scanProgress, resetSheets } = useSheets()
const parameterHelp = [
  ['排除字段', PARAMETER_DESCRIPTIONS.common_cols],
  ['比对表单', PARAMETER_DESCRIPTIONS.sheet_scope],
  ['忽略字段', PARAMETER_DESCRIPTIONS.ignore_settings],
  ['锚点', PARAMETER_DESCRIPTIONS.anchor_settings],
  ['表单顺序', PARAMETER_DESCRIPTIONS.sheet_order],
]

const helpVisible = ref(false)
const settingsVisible = ref(false)
const passwordVisible = ref(false)
const passwordForm = ref({ current_password: '', new_password: '' })
const authReady = ref(false)

onMounted(async () => {
  try {
    await auth.loadCurrentUser()
  } catch (_err) {
    // 登录页展示认证失败，不需要额外提示
  } finally {
    authReady.value = true
  }
})

async function startCompare() {
  if (!config.old_file_upload_id || !config.new_file_upload_id) {
    ElMessage.warning('请先上传旧版本文件与新版本文件')
    return
  }
  try {
    const savedName = await autoSaveBeforeStart()
    if (!savedName) return
    await job.submit(buildJobPayload())
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

async function changePassword() {
  try {
    await auth.changePassword(
      passwordForm.value.current_password,
      passwordForm.value.new_password
    )
    passwordVisible.value = false
    passwordForm.value = { current_password: '', new_password: '' }
    ElMessage.success('密码已修改，请重新登录')
  } catch (err) {
    ElMessage.error(err.message)
  }
}

function logout() {
  auth.logout()
  resetSheets()
  job.reset()
}
</script>

<template>
  <LoginView v-if="authReady && !isAuthenticated" @logged-in="auth.loadCurrentUser" />
  <template v-else-if="authReady && isAuthenticated">
    <template v-if="isAdmin">
      <header class="app-header">
        <h1>数据集比对工具</h1>
        <div class="header-actions">
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
            title="修改密码"
            aria-label="修改密码"
            @click="passwordVisible = true"
          >
            <el-icon :size="16"><Lock /></el-icon>
          </button>
          <button
            class="icon-btn"
            title="退出登录"
            aria-label="退出登录"
            @click="logout"
          >
            <el-icon :size="16"><SwitchButton /></el-icon>
          </button>
        </div>
      </header>
      <div class="app-admin">
        <UserAdminView />
      </div>
    </template>
    <template v-else>
    <header class="app-header">
    <h1>数据集比对工具</h1>
    <div class="header-actions">
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
      <button
        class="icon-btn"
        title="修改密码"
        aria-label="修改密码"
        @click="passwordVisible = true"
      >
        <el-icon :size="16"><Lock /></el-icon>
      </button>
      <button
        class="icon-btn"
        title="退出登录"
        aria-label="退出登录"
        @click="logout"
      >
        <el-icon :size="16"><SwitchButton /></el-icon>
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
        :has-logs="job.logLines.value.length > 0"
        :scanning="scanning"
        :scan-progress="scanProgress"
        @start="startCompare"
        @stop="stopCompare"
        @download-logs="job.downloadLogs()"
        @download-report="downloadReport"
      />
      <CompareForm
        :config="config"
        @update:config="updateConfig"
        @config-changed="() => {}"
      />
    </main>
  </div>

  <el-dialog
    v-model="helpVisible"
    class="help-dialog"
    title="使用帮助"
    width="800px"
    append-to-body
  >
    <div class="help-body">
      <h4>🔧 数据集比对工具使用帮助</h4>

      <h4>🚀 使用步骤</h4>
      <ol>
        <li>在「比对文件」卡片中上传旧版本文件和新版本文件，支持 .xlsx / .xls 格式。</li>
        <li>在「结构设置」中设置锚点行号、表头行号，并选择保留或舍弃删除数据。</li>
        <li>在「颜色设置」中设置更新、删除、新增内容的标记颜色。</li>
        <li>在「比对参数」中按需设置排除字段、排除表单、默认锚点及其他表单范围参数。</li>
        <li>点击「保存配置」保存参数；点击进度卡片中的「开始比对」开始处理。</li>
        <li>比对过程中可点击「停止比对」；完成后点击「下载报告」获取 Excel 结果。</li>
      </ol>
      <p>
        开始比对时会自动保存当前配置。上传文件和配置保存在服务器临时目录中，刷新页面后会自动恢复最近使用的配置；如果文件已过期或被删除，需要重新上传。
      </p>

      <h4>🧰 配置管理</h4>
      <ul>
        <li><b>新建：</b>点击「新建配置」，输入名称；也可以在弹窗左下角选择 TM 或 CIMS 模板导入参数。</li>
        <li><b>保存：</b>在「比对参数」卡片底部点击「保存配置」，保存当前参数与已上传文件。</li>
        <li><b>取消保存：</b>撤销最近一次保存之后的修改，恢复到当前配置的已保存状态。</li>
        <li><b>复制：</b>点击配置名称右侧的复制按钮，输入新名称即可复制当前配置。</li>
        <li><b>删除：</b>点击配置名称右侧的删除按钮，删除选中的配置。</li>
        <li><b>导入：</b>使用配置管理区域的导入按钮，从 JSON 文件导入配置。</li>
        <li><b>导出：</b>选中配置后使用导出按钮，将配置保存为 JSON 文件。</li>
        <li>内置 TM / CIMS 模板只在新建配置弹窗中使用，不会出现在配置列表中。</li>
      </ul>

      <h4>🔧 参数设置</h4>
      <ul>
        <li><b>旧版本文件 / 新版本文件：</b>待比较的两个 Excel 文件。文件上传后会暂存在服务器。</li>
        <li><b>锚点行号：</b>锚点及删除列数据所在行的行号。</li>
        <li><b>表头行号：</b>输出文件表头所在行的行号。</li>
        <li><b>保留删除数据：</b>开启时保留新版本中不存在的表单、行和列；关闭时舍弃这些删除数据。</li>
        <li v-for="[title, description] in parameterHelp" :key="title">
          <b>{{ title }}：</b>{{ description }}
        </li>
        <li><b>颜色：</b>更新颜色标记有差异的单元格和 Sheet；删除颜色标记旧版本存在而新版本不存在的 Sheet 和列；新增颜色标记旧版本不存在而新版本存在的 Sheet 和列。</li>
      </ul>

      <h4>🎛 高级设置</h4>
      <ul>
        <li><b>最大线程数：</b>控制同时处理的 Sheet 数量，默认值为 4；通常不建议超过 CPU 核心数的两倍。</li>
        <li><b>深色模式：</b>点击页面右上角的主题按钮，或在高级设置中切换界面主题。</li>
        <li><b>比对状态：</b>进度卡片显示等待、处理中、完成、失败或停止状态；完成后仍可点击「开始比对」再次运行。</li>
      </ul>

      <h4>📝 日志记录</h4>
      <ul>
        <li>比对过程中的处理信息会实时显示在进度卡片中，并由服务器任务持续返回。</li>
        <li>有日志内容时，点击进度卡片中的「下载日志」按钮即可保存文本日志。</li>
        <li>日志包含处理过程和错误信息，可用于问题排查；若任务失败，请先查看日志中的具体提示。</li>
      </ul>

      <p class="help-footer">
        作者：Decade<br />
        联系方式：jian.tan@zzmedicine.cn<br />
        项目主页：<a href="https://github.com/decade6666/Data-Comparator" target="_blank" rel="noreferrer">https://github.com/decade6666/Data-Comparator</a>
      </p>
    </div>
  </el-dialog>

  <NewConfigDialog />

  <AdvancedSettingsDialog
    v-model="settingsVisible"
    :max-workers="config.max_workers"
    :is-dark="isDark"
    @update:max-workers="applyMaxWorkers"
    @update:is-dark="toggleTheme"
  />
  </template>

  <el-dialog v-model="passwordVisible" title="修改密码" width="420px" append-to-body>
    <el-form label-position="top" @submit.prevent="changePassword">
      <el-form-item label="当前密码">
        <el-input v-model="passwordForm.current_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码（至少 8 位）">
        <el-input v-model="passwordForm.new_password" type="password" show-password />
      </el-form-item>
      <el-button type="primary" @click="changePassword">确认修改</el-button>
    </el-form>
  </el-dialog>
  </template>
</template>

<style scoped>
.help-body {
  max-height: min(70vh, 680px);
  overflow-y: auto;
  padding-right: 8px;
}

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

.help-body p {
  margin: 8px 0;
}

.help-body .help-footer {
  color: var(--color-text-secondary);
  line-height: 1.8;
}

.help-body a {
  color: var(--color-primary);
}
</style>
