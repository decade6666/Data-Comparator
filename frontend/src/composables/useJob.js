import { ref } from 'vue'
import { api } from './useApi'

const POLL_INTERVAL_MS = 1000

export function useJob() {
  const jobId = ref(null)
  const status = ref('idle') // idle | pending | running | completed | failed | cancelled
  const progress = ref(0)
  const progressMessage = ref('准备就绪')
  const logLines = ref([])
  const logCursor = ref(0)
  const outputPath = ref(null)
  const error = ref(null)
  const outputName = ref('')

  let pollTimer = null

  function _stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function _poll() {
    if (!jobId.value) return
    let body
    try {
      body = await api.get(
        `/jobs/${jobId.value}?since=${logCursor.value}`
      )
    } catch (err) {
      // 轮询失败时保留最后一次已知状态
      return
    }
    if (body.status !== status.value) status.value = body.status
    if (body.progress_percent != null) progress.value = body.progress_percent
    if (body.progress_message) progressMessage.value = body.progress_message
    if (body.log_lines && body.log_lines.length) {
      logLines.value.push(...body.log_lines)
      logCursor.value = body.log_cursor
    }
    if (body.output_path) {
      outputPath.value = body.output_path
      outputName.value = body.output_path.split('/').pop() || '比对报告.xlsx'
    }
    if (body.error) error.value = body.error
    if (['completed', 'failed', 'cancelled'].includes(body.status)) {
      _stopPolling()
    }
  }

  async function submit(params) {
    reset()
    const body = await api.post('/jobs', params)
    jobId.value = body.job_id
    status.value = 'pending'
    pollTimer = setInterval(_poll, POLL_INTERVAL_MS)
  }

  async function cancel() {
    if (!jobId.value) return
    await api.post(`/jobs/${jobId.value}/cancel`)
    status.value = 'cancelling'
  }

  function reset() {
    _stopPolling()
    jobId.value = null
    status.value = 'idle'
    progress.value = 0
    progressMessage.value = '准备就绪'
    logLines.value = []
    logCursor.value = 0
    outputPath.value = null
    error.value = null
    outputName.value = ''
  }

  function download() {
    if (!jobId.value) return
    window.open(api.apiUrl(`/jobs/${jobId.value}/download`), '_blank')
  }

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
    reset,
  }
}
