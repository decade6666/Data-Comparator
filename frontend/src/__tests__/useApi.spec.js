import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, detectBasePath } from '../composables/useApi'

function makeResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: vi.fn(() => null) },
    text: vi.fn(async () => body),
  }
}

describe('detectBasePath', () => {
  it('derives a mounted base path from the asset module URL', () => {
    expect(
      detectBasePath('https://example.test/dataset/assets/index-abc.js')
    ).toBe('/dataset/')
  })

  it('derives the root path for root-mounted assets', () => {
    expect(detectBasePath('https://example.test/assets/index-abc.js')).toBe('/')
  })

  it('prefers an explicitly configured base path', () => {
    expect(
      detectBasePath(
        'https://example.test/dataset/assets/index-abc.js',
        '/configured/'
      )
    ).toBe('/configured/')
  })
})

describe('api error responses', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps an unknown JSON error body for troubleshooting', async () => {
    fetch.mockResolvedValue(makeResponse(404, '{"error":"not_found"}'))

    await expect(api.post('/auth/login', { username: 'x', password: 'y' })).rejects.toThrow(
      '请求失败 (404): {"error":"not_found"}'
    )
  })

  it('keeps a short non-JSON error body for troubleshooting', async () => {
    fetch.mockResolvedValue(makeResponse(502, 'upstream unavailable'))

    await expect(api.get('/health')).rejects.toThrow(
      '请求失败 (502): upstream unavailable'
    )
  })
})
