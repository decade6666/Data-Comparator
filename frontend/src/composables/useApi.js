// 挂载前缀运行时推导：优先构建期显式配置，否则由自身模块 URL 回溯到挂载根，
// 使同一份产物在根路径直连与子路径反代下都能拼出正确的 API 地址。
function detectBasePath(
  moduleUrl = import.meta.url,
  configured = import.meta.env?.VITE_BASE_PATH
) {
  if (configured) return configured
  try {
    const parsedUrl = new URL(moduleUrl)
    if (parsedUrl.protocol === 'file:') return ''
    if (parsedUrl.pathname.includes('/assets/')) {
      return new URL('../', parsedUrl).pathname
    }
    // Vite 开发态模块位于 /src/...，使用页面地址保留子路径。
    if (typeof document !== 'undefined' && document.baseURI) {
      return new URL('./', document.baseURI).pathname
    }
    return new URL('../', parsedUrl).pathname
  } catch (_err) {
    return ''
  }
}

function buildApiBase(base) {
  if (!base) return '/api'
  const normalizedBase =
    base === './' || base.startsWith('/') || base.includes('://')
      ? base
      : `/${base}`
  return (normalizedBase.endsWith('/') ? normalizedBase : normalizedBase + '/') + 'api'
}

const API_BASE = buildApiBase(detectBasePath())
const TOKEN_KEY = 'dc_token'

function apiUrl(path) {
  return API_BASE + path
}

function authHeaders(headers = {}) {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return headers
  return { ...headers, Authorization: `Bearer ${token}` }
}

function formatErrorBody(text) {
  const maxLength = 200
  return text.length > maxLength ? text.slice(0, maxLength) + '…' : text
}

async function request(method, path, options = {}) {
  let response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: authHeaders(options.headers),
      body: options.body,
    })
  } catch (err) {
    throw new Error('无法连接服务器: ' + err.message)
  }

  const refreshedToken = response.headers.get('X-Refreshed-Token')
  if (refreshedToken) localStorage.setItem(TOKEN_KEY, refreshedToken)

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new CustomEvent('dc-auth-expired'))
    }
    let detail = '请求失败 (' + response.status + ')'
    try {
      const text = (await response.text()).trim()
      if (text) {
        try {
          const data = JSON.parse(text)
          if (data && data.detail) {
            detail =
              typeof data.detail === 'string'
                ? data.detail
                : JSON.stringify(data.detail)
          } else {
            detail += ': ' + formatErrorBody(text)
          }
        } catch (_jsonErr) {
          detail += ': ' + formatErrorBody(text)
        }
      }
    } catch (_err) {
      // 保留默认错误信息
    }
    throw new Error(detail)
  }
  return response
}

async function get(path) {
  const response = await request('GET', path)
  return response.json()
}

async function post(path, body) {
  const response = await request('POST', path, {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response.status === 204) return null
  return response.json()
}

async function put(path, body) {
  const response = await request('PUT', path, {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response.status === 204) return null
  return response.json()
}

async function del(path) {
  const response = await request('DELETE', path)
  if (response.status === 204) return null
  return response.json()
}

async function postForm(path, formData) {
  const response = await request('POST', path, { body: formData })
  return response.json()
}

function parseFilenameFromCD(header) {
  if (!header) return null
  const encoded = /filename\*=utf-8''([^;]+)/i.exec(header)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim())
    } catch (_err) {
      // 回退到明文 filename 解析
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain ? plain[1].trim() : null
}

async function download(path, fallbackFilename = 'download') {
  const response = await request('GET', path)
  const blob = await response.blob()
  const filename =
    parseFilenameFromCD(response.headers.get('content-disposition')) ||
    fallbackFilename
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

export const api = {
  apiUrl,
  get,
  post,
  put,
  del,
  postForm,
  download,
}

export { detectBasePath }
