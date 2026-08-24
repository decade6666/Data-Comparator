import { computed, reactive, ref } from 'vue'
import { api } from './useApi'

const POLL_INTERVAL_MS = 1000
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])

function blankEntry() {
  return {
    jobId: null,
    status: 'idle', // idle | pending | running | completed | failed | cancelled | cancelling
    progress: 0,
    progressMessage: '准备就绪',
    logLines: [],
    logCursor: 0,
    outputPath: null,
    outputName: '',
    error: null,
  }
}

// 任务状态按项目名分桶：切走项目不丢它的报告与日志，切回来仍可下载。
const entries = reactive({})
const activeKey = ref('') // '' 表示尚未命名的项目

function entryOf(key) {
  if (!(key in entries)) entries[key] = blankEntry()
  return entries[key]
}

const current = computed(() => entryOf(activeKey.value))

// 对外暴露 computed ref，App.vue 的 job.status.value 等写法保持不变。
const jobId = computed(() => current.value.jobId)
const status = computed(() => current.value.status)
const progress = computed(() => current.value.progress)
const progressMessage = computed(() => current.value.progressMessage)
const logLines = computed(() => current.value.logLines)
const outputPath = computed(() => current.value.outputPath)
const outputName = computed(() => current.value.outputName)
const error = computed(() => current.value.error)

let pollTimer = null

function _stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function _startPolling() {
  _stopPolling()
  pollTimer = setInterval(_poll, POLL_INTERVAL_MS)
}

// 终态回调：轮询检测到任一任务（含已切走的项目）进入终态时触发，
// 传入冻结快照供自动下载使用，不依赖当前活跃项目。
let _onTerminal = null

function setOnTerminal(cb) {
  _onTerminal = cb
}

async function _poll() {
  const snapshotEntries = []
  for (const [key, entry] of Object.entries(entries)) {
    if (!entry.jobId || TERMINAL_STATUSES.has(entry.status)) continue
    try {
      const body = await api.get(`/jobs/${entry.jobId}?since=${entry.logCursor}`)
      if (!body || !(key in entries)) continue // 轮询期间项目被删除，丢弃结果
      const target = entries[key]
      if (body.status !== target.status) target.status = body.status
      if (body.progress_percent != null) target.progress = body.progress_percent
      if (body.progress_message) target.progressMessage = body.progress_message
      if (body.log_lines && body.log_lines.length) {
        target.logLines.push(...body.log_lines)
        target.logCursor = body.log_cursor
      }
      if (body.output_path) {
        target.outputPath = body.output_path
        target.outputName = body.output_path.split('/').pop() || '比对报告.xlsx'
      }
      if (body.error) target.error = body.error
      if (TERMINAL_STATUSES.has(body.status)) {
        // 冻结快照：自动下载用提交/完成时刻的值，重提同项目不干扰
        snapshotEntries.push({
          jobId: target.jobId,
          status: target.status,
          outputName: target.outputName,
          logLines: [...target.logLines],
        })
      }
    } catch (err) {
      // 轮询失败时保留最后一次已知状态
    }
  }
  if (_onTerminal) {
    for (const snapshot of snapshotEntries) _onTerminal(snapshot)
  }
  _ensurePolling()
}

function _ensurePolling() {
  const anyActive = Object.values(entries).some(
    (entry) => entry.jobId && !TERMINAL_STATUSES.has(entry.status)
  )
  if (anyActive) _startPolling()
  else _stopPolling()
}

async function submit(params) {
  const key = activeKey.value
  reset()
  const body = await api.post('/jobs', params)
  if (!(key in entries)) entries[key] = blankEntry() // submit 期间桶被清空则重建
  entries[key].jobId = body.job_id
  entries[key].status = 'pending'
  _ensurePolling()
  return body.job_id // 返回刚提交任务 id，供调用方绑定（不读当前项目）
}

async function cancel() {
  if (!jobId.value) return
  await api.post(`/jobs/${jobId.value}/cancel`)
  current.value.status = 'cancelling'
}

function reset() {
  const entry = current.value
  entry.jobId = null
  entry.status = 'idle'
  entry.progress = 0
  entry.progressMessage = '准备就绪'
  entry.logLines = []
  entry.logCursor = 0
  entry.outputPath = null
  entry.error = null
  entry.outputName = ''
}

function activateJob(name) {
  // 不停止轮询：轮询按任务（而非活跃项目）驱动，切走后任务仍在轮询
  activeKey.value = name
  _ensurePolling()
}

function dropJob(name) {
  delete entries[name]
  if (activeKey.value === name) activeKey.value = ''
  _ensurePolling()
}

function renameJob(from, to) {
  if (from === to) return
  if (from in entries) {
    entries[to] = entries[from]
    delete entries[from]
  }
  if (activeKey.value === from) activeKey.value = to
}

function resetAllJobs() {
  _stopPolling()
  for (const key of Object.keys(entries)) {
    delete entries[key]
  }
  activeKey.value = ''
}

// 按 jobId 定位条目（不依赖当前活跃项目）；缺失返回 undefined。
function entryFor(jobId) {
  return Object.values(entries).find((entry) => entry.jobId === jobId)
}

async function download() {
  if (!jobId.value) return
  await downloadFor(current.value)
}

async function downloadFor(entry) {
  if (!entry || !entry.jobId) return
  await api.download(
    `/jobs/${entry.jobId}/download`,
    entry.outputName || '比对报告.xlsx'
  )
}

// 优先下载服务端落盘的日志文件；服务端不可用时退回浏览器内存 Blob
async function downloadLogs() {
  if (!logLines.value.length) return
  await downloadLogsFor(current.value)
}

async function downloadLogsFor(entry) {
  if (!entry || !entry.jobId) return
  try {
    await api.download(
      `/jobs/${entry.jobId}/log`,
      `比对日志-${entry.outputName || 'log'}.txt`,
    )
  } catch (_err) {
    const blob = new Blob([entry.logLines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `比对日志-${entry.outputName || 'log'}.txt`
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }
}

export { activateJob, dropJob, renameJob, resetAllJobs }

export function useJob() {
  return {
    jobId,
    status,
    progress,
    progressMessage,
    logLines,
    outputPath,
    outputName,
    error,
    submit,
    cancel,
    download,
    downloadLogs,
    entryFor,
    downloadFor,
    downloadLogsFor,
    setOnTerminal,
    reset,
    activateJob,
    dropJob,
    renameJob,
    resetAllJobs,
  }
}
