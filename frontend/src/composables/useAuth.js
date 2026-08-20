import { ref, computed } from 'vue'
import { api } from './useApi'

const TOKEN_KEY = 'dc_token'
const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref(null)
// computed 放在模块作用域：每次 useAuth() 调用共享同一实例，
// 解构 computed ref 是安全的（拷贝的是 ref 对象本身，不是值）；
// 若解构普通值属性会丢失响应性。
const isAuthenticated = computed(() => Boolean(token.value && user.value))
const isAdmin = computed(() => Boolean(user.value?.is_admin))

function setToken(value) {
  token.value = value || ''
  if (token.value) localStorage.setItem(TOKEN_KEY, token.value)
  else localStorage.removeItem(TOKEN_KEY)
}

function setUser(nextUser) {
  user.value = nextUser
  if (nextUser?.username) localStorage.setItem('dc_username', nextUser.username)
  else localStorage.removeItem('dc_username')
}

function clearSession() {
  setToken('')
  setUser(null)
}

export function useAuth() {
  async function login(username, password) {
    const body = await api.post('/auth/login', { username, password })
    setToken(body.access_token)
    await loadCurrentUser()
    return user.value
  }

  async function loadCurrentUser() {
    if (!token.value) {
      user.value = null
      return null
    }
    try {
      setUser(await api.get('/auth/me'))
      return user.value
    } catch (err) {
      clearSession()
      throw err
    }
  }

  async function changePassword(currentPassword, newPassword) {
    await api.put('/auth/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    clearSession()
  }

  function logout() {
    clearSession()
  }

  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    login,
    loadCurrentUser,
    changePassword,
    logout,
  }
}

window.addEventListener('dc-auth-expired', clearSession)

export { TOKEN_KEY, setToken, clearSession }
