const BASE = import.meta.env.VITE_BASE_PATH || ''
const API_BASE = (BASE.endsWith('/') ? BASE : BASE + '/') + 'api'

function apiUrl(path) {
  return API_BASE + path
}

async function request(method, path, options = {}) {
  let response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: options.headers,
      body: options.body,
    })
  } catch (err) {
    throw new Error('无法连接服务器: ' + err.message)
  }
  if (!response.ok) {
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
  return response.json()
}

async function put(path, body) {
  const response = await request('PUT', path, {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return response.json()
}

async function del(path) {
  const response = await request('DELETE', path)
  return response.json()
}

async function postForm(path, formData) {
  const response = await request('POST', path, { body: formData })
  return response.json()
}

export const api = {
  apiUrl,
  get,
  post,
  put,
  del,
  postForm,
}
