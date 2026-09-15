/**
 * restoreActiveJob 启动接管回归测试。
 *
 * 背景：关闭浏览器后前端丢失任务状态而后端仍在跑，重开页面需自动接管
 * /jobs/active 返回的任务（切到任务所属项目并恢复轮询）；无任务时回落
 * restoreLastConfig；stale（占位残留）不切项目，交由调用方提示。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  adoptActiveJob,
  restoreActiveJob,
} from '../composables/useConfigState.js'
import { resetAllJobs } from '../composables/useJob.js'
import { api } from '../composables/useApi.js'

vi.mock('../composables/useApi', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    download: vi.fn(),
  },
}))

function activeBody(overrides = {}) {
  return {
    active: true,
    stale: false,
    job_id: 'job-live',
    config_name: 'A',
    status: 'running',
    progress_percent: 40,
    progress_message: '处理中',
    log_lines: ['log-1'],
    log_cursor: 1,
    output_path: null,
    error: null,
    ...overrides,
  }
}

function routeApiGet(activeResponse) {
  api.get.mockImplementation((path) => {
    if (path === '/jobs/active') return Promise.resolve(activeResponse)
    if (path.startsWith('/configs/')) return Promise.resolve({}) // loadConfig
    return Promise.resolve(null)
  })
}

describe('restoreActiveJob', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    resetAllJobs()
  })

  it('adopts the running job and switches to its config', async () => {
    routeApiGet(activeBody())
    const result = await restoreActiveJob(['A', 'B'])

    expect(result).toBe(true)
    // selectConfig 被调用（loadConfig 拉取了项目 A 的文档）
    expect(api.get).toHaveBeenCalledWith('/configs/A')
    expect(localStorage.getItem('dc_last_config:anonymous')).toBe('A')
  })

  it('adopts into the bucket even when the config no longer exists', async () => {
    routeApiGet(activeBody({ config_name: 'gone' }))
    const result = await restoreActiveJob(['A', 'B'])

    expect(result).toBe(true)
    // 项目不在列表中：不调用 loadConfig，但仍恢复任务到该名称的桶
    expect(api.get).not.toHaveBeenCalledWith('/configs/gone')
  })

  it('falls back to restoreLastConfig when no active job', async () => {
    routeApiGet({ active: false })
    localStorage.setItem('dc_last_config:anonymous', 'B')
    api.get.mockImplementation((path) => {
      if (path === '/jobs/active') return Promise.resolve({ active: false })
      if (path === '/configs') return Promise.resolve(['B'])
      if (path.startsWith('/configs/')) return Promise.resolve({})
      return Promise.resolve(null)
    })

    const result = await restoreActiveJob(['B'])
    expect(result).toBe(false)
    expect(localStorage.getItem('dc_last_config:anonymous')).toBe('B')
  })

  it("returns 'stale' without switching config", async () => {
    routeApiGet(activeBody({ active: true, stale: true, config_name: 'A' }))
    const result = await restoreActiveJob(['A'])

    expect(result).toBe('stale')
    expect(api.get).not.toHaveBeenCalledWith('/configs/A')
    expect(localStorage.getItem('dc_last_config:anonymous')).toBeNull()
  })

  it('silently falls back when the endpoint is missing (old backend 404)', async () => {
    const notFound = new Error('请求失败 (404)')
    notFound.status = 404
    api.get.mockImplementation((path) => {
      if (path === '/jobs/active') return Promise.reject(notFound)
      if (path === '/configs') return Promise.resolve([])
      return Promise.resolve(null)
    })

    const result = await restoreActiveJob([])
    expect(result).toBe(false)
  })

  it('rethrows non-404 errors', async () => {
    const boom = new Error('无法连接服务器: x')
    boom.status = undefined
    api.get.mockRejectedValue(boom)

    await expect(restoreActiveJob([])).rejects.toThrow('无法连接服务器')
  })
})

// adoptActiveJob 是 409 兜底「先接管、后询问」的第一步：直接暴露四种
// 结果（true / 'stale' / 'none' / 'unavailable'），不回落恢复上次项目。
describe('adoptActiveJob', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    resetAllJobs()
  })

  it('adopts the active task and switches to its config', async () => {
    routeApiGet(activeBody())
    const result = await adoptActiveJob(['A', 'B'])

    expect(result).toBe(true)
    // selectConfig 被调用（loadConfig 拉取了项目 A 的文档）
    expect(api.get).toHaveBeenCalledWith('/configs/A')
    expect(localStorage.getItem('dc_last_config:anonymous')).toBe('A')
  })

  it("returns 'none' when the backend has no active job", async () => {
    routeApiGet({ active: false })
    const result = await adoptActiveJob(['A', 'B'])

    expect(result).toBe('none')
    expect(api.get).not.toHaveBeenCalledWith('/configs/A')
    expect(localStorage.getItem('dc_last_config:anonymous')).toBeNull()
  })

  it("returns 'stale' without switching config", async () => {
    routeApiGet(activeBody({ active: true, stale: true, config_name: 'A' }))
    const result = await adoptActiveJob(['A'])

    expect(result).toBe('stale')
    expect(api.get).not.toHaveBeenCalledWith('/configs/A')
    expect(localStorage.getItem('dc_last_config:anonymous')).toBeNull()
  })

  it("returns 'unavailable' when the endpoint is missing (old backend 404)", async () => {
    const notFound = new Error('请求失败 (404)')
    notFound.status = 404
    api.get.mockRejectedValue(notFound)

    const result = await adoptActiveJob(['A'])
    expect(result).toBe('unavailable')
  })

  it('rethrows non-404 errors', async () => {
    const boom = new Error('服务器内部错误')
    boom.status = 500
    api.get.mockRejectedValue(boom)

    await expect(adoptActiveJob(['A'])).rejects.toThrow('服务器内部错误')
  })
})
