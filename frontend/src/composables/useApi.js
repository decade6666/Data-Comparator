const BASE = (import.meta.env?.VITE_BASE_PATH) || ''
const API_BASE = (BASE.endsWith('/') ? BASE : BASE + '/') + 'api'
const TOKEN_KEY = 'dc_token'

function apiUrl(path) {
  return API_BASE + path
}

function authHeaders(headers = {}) {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return headers
  return { ...headers, Authorization: `Bearer ${token}` }
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
      const data = await response.json()
      if (data && data.detail) {
        detail =
          typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail)
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
