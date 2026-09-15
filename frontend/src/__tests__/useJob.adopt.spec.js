/**
 * useJob 接管回归测试。
 *
 * 背景：任务状态纯内存，关闭浏览器后前端丢失 jobId，而后端任务仍在运行
 * 并占用槽位，用户被 409 挡住且无法取消。新增 adoptJob（把 /jobs/active
 * 快照灌回项目桶并恢复轮询）与 cancelActive（不依赖 jobId 的兜底取消）。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useJob } from '../composables/useJob'
import { api } from '../composables/useApi'

vi.mock('../composables/useApi', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    download: vi.fn(),
  },
}))

const RUNNING_BODY = {
  job_id: 'job-adopt',
  status: 'running',
  progress_percent: 62,
  progress_message: '处理表单 AE',
  log_lines: ['line-1', 'line-2'],
  log_cursor: 2,
  output_path: null,
  error: null,
}

describe('useJob adoptJob / cancelActive', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('adoptJob restores status, progress and logs into the bucket', () => {
    const job = useJob()
    job.activateJob('A')
    job.adoptJob('A', RUNNING_BODY)

    expect(job.jobId.value).toBe('job-adopt')
    expect(job.status.value).toBe('running')
    expect(job.progress.value).toBe(62)
    expect(job.progressMessage.value).toBe('处理表单 AE')
    expect(job.logLines.value).toEqual(['line-1', 'line-2'])
    expect(job.outputPath.value).toBeNull()
  })

  it('adoptJob resumes polling and cancel() works without resubmitting', async () => {
    const job = useJob()
    job.activateJob('A')
    job.adoptJob('A', RUNNING_BODY)
    api.get.mockResolvedValueOnce({
      job_id: 'job-adopt',
      status: 'running',
      progress_percent: 80,
      progress_message: '处理表单 BB',
      log_lines: ['line-3'],
      log_cursor: 3,
      output_path: null,
    })

    await vi.advanceTimersByTimeAsync(1100)

    expect(api.get).toHaveBeenCalledWith('/jobs/job-adopt?since=2')
    expect(job.progress.value).toBe(80)
    expect(job.logLines.value).toEqual(['line-1', 'line-2', 'line-3'])

    // 接管后取消不需要重新提交
    api.post.mockResolvedValueOnce({ job_id: 'job-adopt', status: 'cancelling' })
    await job.cancel()
    expect(api.post).toHaveBeenCalledWith('/jobs/job-adopt/cancel')
    expect(job.status.value).toBe('cancelling')
  })

  it('cancelActive posts to the id-less active cancel endpoint', async () => {
    const job = useJob()
    api.post.mockResolvedValueOnce({ job_id: 'job-adopt', status: 'cancelling' })
    await job.cancelActive()
    expect(api.post).toHaveBeenCalledWith('/jobs/active/cancel')
  })

  it('adoptJob tolerates a snapshot without logs or progress', () => {
    const job = useJob()
    job.activateJob('A')
    job.adoptJob('A', { job_id: 'job-adopt', status: 'pending' })

    expect(job.jobId.value).toBe('job-adopt')
    expect(job.status.value).toBe('pending')
    expect(job.progress.value).toBe(0)
    expect(job.progressMessage.value).toBe('比对进行中')
    expect(job.logLines.value).toEqual([])
  })
})
