/**
 * useJob 按项目分桶回归测试。
 *
 * 背景：任务状态原为单一实例，切换项目不重置，下载与日志导出仍指向
 * 上一个项目。修复后每个项目名独立保存任务记录（jobId/status/日志），
 * 切回原项目仍可下载它自己的报告与日志。
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

describe('useJob per-config buckets', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    api.get.mockResolvedValue({
      job_id: 'job-A',
      status: 'completed',
      progress_percent: 100,
      progress_message: '完成',
      log_lines: ['line-1', 'line-2'],
      log_cursor: 2,
      output_path: '/tmp/A-比对报告.xlsx',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps per-project job id, status and logs across switches', async () => {
    const job = useJob()
    // 在 A 下提交并轮询到完成
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    expect(job.jobId.value).toBe('job-A')
    await vi.advanceTimersByTimeAsync(1100)
    expect(job.status.value).toBe('completed')
    expect(job.logLines.value).toEqual(['line-1', 'line-2'])
    expect(job.outputName.value).toBe('A-比对报告.xlsx')

    // 切到 B：idle、无 jobId、无日志
    job.activateJob('B')
    expect(job.status.value).toBe('idle')
    expect(job.jobId.value).toBeNull()
    expect(job.logLines.value).toEqual([])

    // 切回 A：恢复 A 自己的记录
    job.activateJob('A')
    expect(job.jobId.value).toBe('job-A')
    expect(job.status.value).toBe('completed')
    expect(job.logLines.value).toEqual(['line-1', 'line-2'])
  })

  it('download targets the currently active project job id', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    await vi.advanceTimersByTimeAsync(1100)
    api.download.mockResolvedValueOnce(undefined)

    await job.download()
    expect(api.download).toHaveBeenCalledWith(
      '/jobs/job-A/download',
      'A-比对报告.xlsx'
    )

    api.download.mockClear()
    job.activateJob('B')
    await job.download()
    expect(api.download).not.toHaveBeenCalled()
  })

  it('dropJob removes a bucket and clears active job state', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    job.dropJob('A')
    expect(job.jobId.value).toBeNull()
    expect(job.status.value).toBe('idle')
    job.activateJob('A')
    expect(job.jobId.value).toBeNull()
  })

  it('renameJob migrates bucket content and active key', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    await vi.advanceTimersByTimeAsync(1100)

    job.renameJob('A', 'A2')
    expect(job.jobId.value).toBe('job-A')
    expect(job.status.value).toBe('completed')

    job.activateJob('A')
    expect(job.jobId.value).toBeNull()
    job.activateJob('A2')
    expect(job.jobId.value).toBe('job-A')
  })

  it('resetAllJobs clears every bucket and active key', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    await vi.advanceTimersByTimeAsync(1100)
    job.activateJob('B')
    job.resetAllJobs()
    expect(job.jobId.value).toBeNull()
    expect(job.status.value).toBe('idle')
    job.activateJob('A')
    expect(job.jobId.value).toBeNull()
  })

  it('poll result written back to the key captured at request start (race)', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    // 第一次轮询请求挂起（不 resolve）
    let resolvePoll
    api.get.mockReturnValue(
      new Promise((resolve) => {
        resolvePoll = resolve
      })
    )
    await job.submit({ a: 1 })
    await vi.advanceTimersByTimeAsync(1100)

    // 请求在途时切换到 B
    job.activateJob('B')
    // 迟到的响应写回 A 的桶，而不是 B
    resolvePoll({
      job_id: 'job-A',
      status: 'completed',
      progress_percent: 100,
      progress_message: '完成',
      log_lines: ['late-line'],
      log_cursor: 1,
      output_path: '/tmp/A-比对报告.xlsx',
    })
    await vi.advanceTimersByTimeAsync(0)

    expect(job.status.value).toBe('idle')
    expect(job.logLines.value).toEqual([])
    job.activateJob('A')
    expect(job.status.value).toBe('completed')
    expect(job.logLines.value).toEqual(['late-line'])
  })

  it('terminal callback fires for a task after switching away (切走仍触发)', async () => {
    const job = useJob()
    const onTerminal = vi.fn()
    job.setOnTerminal(onTerminal)

    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    await job.submit({ a: 1 })
    await vi.advanceTimersByTimeAsync(1100)

    // 切走 A，轮询不停止；A 的终态在后台被检测到并触发回调
    job.activateJob('B')
    await vi.advanceTimersByTimeAsync(1100)

    expect(onTerminal).toHaveBeenCalledTimes(1)
    const snapshot = onTerminal.mock.calls[0][0]
    expect(snapshot.jobId).toBe('job-A')
    expect(snapshot.status).toBe('completed')
    expect(snapshot.outputName).toBe('A-比对报告.xlsx')
    expect(snapshot.logLines).toEqual(['line-1', 'line-2'])
  })

  it('submit returns the newly submitted job id', async () => {
    const job = useJob()
    job.activateJob('A')
    api.post.mockResolvedValueOnce({ job_id: 'job-A', status: 'pending' })
    const jobId = await job.submit({ a: 1 })
    expect(jobId).toBe('job-A')
  })
})
