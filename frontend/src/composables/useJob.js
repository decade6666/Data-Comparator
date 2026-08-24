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

async function _poll() {
  const key = activeKey.value // 进入时捕获归属，防止在途切换项目写串
  if (!key || !(key in entries)) return
  const entry = entries[key]
  if (!entry.jobId) return
  try {
    const body = await api.get(`/jobs/${entry.jobId}?since=${entry.logCursor}`)
    if (!body) return
    if (!(key in entries)) return // 轮询期间项目被删除，丢弃结果
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
      // 已切走的项目完成时不停掉新项目的轮询
      if (activeKey.value === key) _stopPolling()
    }
  } catch (err) {
    // 轮询失败时保留最后一次已知状态
  }
}

async function submit(params) {
  const key = activeKey.value
  reset()
  const body = await api.post('/jobs', params)
  if (!(key in entries)) entries[key] = blankEntry() // submit 期间桶被清空则重建
  entries[key].jobId = body.job_id
  entries[key].status = 'pending'
  _startPolling()
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
  _stopPolling()
  activeKey.value = name
  const entry = entryOf(name)
  if (entry.jobId && !TERMINAL_STATUSES.has(entry.status)) {
    _startPolling()
  }
}

function dropJob(name) {
  if (activeKey.value === name) _stopPolling()
  delete entries[name]
  if (activeKey.value === name) activeKey.value = ''
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

async function download() {
  if (!jobId.value) return
  await api.download(
    `/jobs/${jobId.value}/download`,
    outputName.value || '比对报告.xlsx'
  )
}

// 将累积的日志行导出为 .txt 文件（纯前端 Blob 下载，无需后端端点）
function downloadLogs() {
  if (!logLines.value.length) return
  const blob = new Blob([logLines.value.join('\n')], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `比对日志-${outputName.value || 'log'}.txt`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
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
    reset,
    activateJob,
    dropJob,
    renameJob,
    resetAllJobs,
  }
}
