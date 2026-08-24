/**
 * App.vue 登录守卫回归测试。
 *
 * 背景：`auth.isAuthenticated` / `auth.isAdmin` 是嵌套在普通对象里的 computed ref，
 * 模板中 `_unref(auth).isAuthenticated` 拿到的是 ref 对象本身（恒为真），
 * 导致未登录也渲染主界面、任何用户都看到管理员按钮。
 * 修复要求：解构成顶层绑定 `isAuthenticated` / `isAdmin` 后再用于模板。
 *
 * 管理员登录后直接渲染用户管理界面（App.vue 的 v-if="isAdmin" 分支），
 * 该分支真实挂载 UserAdminView，其 onMounted 会请求 GET /api/users；
 * 因此 fetch 桩需按 URL 路由，分别应答 /auth/me（对象）与 /users（数组）。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { h } from 'vue'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')) },
}))

// element-plus 被 mock 后 el-table/el-table-column 无法解析，模板中
// #default="{ row }" 作用域插槽会因 slot() 无参调用而崩溃；这里提供
// 最小 el-* 打桩（el-table 逐行渲染列插槽并注入 row 作用域）。
const elStubs = {
  'el-table': {
    name: 'ElTableStub',
    props: { data: { type: Array, default: () => [] }, loading: { type: Boolean, default: false } },
    setup(props, { slots }) {
      return () => {
        const columns = (slots.default ? slots.default() : []).filter(Boolean)
        return h(
          'div',
          { class: 'el-table-stub' },
          props.data.flatMap((row) =>
            columns.map((col) =>
              h(col.type, { ...(col.props || {}), row }, col.children || null)
            )
          )
        )
      }
    },
  },
  'el-table-column': {
    name: 'ElTableColumnStub',
    props: ['prop', 'label', 'width', 'minWidth', 'row'],
    setup(props, { slots }) {
      return () =>
        h(
          'div',
          { class: 'el-table-column-stub' },
          slots.default ? slots.default(props) : [props.label]
        )
    },
  },
  'el-button': {
    name: 'ElButtonStub',
    props: ['type', 'icon', 'loading', 'disabled', 'link', 'size'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-tooltip': {
    name: 'ElTooltipStub',
    template: '<span class="el-tooltip-stub"><slot /></span>',
  },
  'el-tag': {
    name: 'ElTagStub',
    template: '<span class="el-tag-stub"><slot /></span>',
  },
  'el-icon': {
    name: 'ElIconStub',
    template: '<span class="el-icon-stub"><slot /></span>',
  },
  'el-dialog': {
    name: 'ElDialogStub',
    props: ['modelValue', 'title', 'width', 'appendToBody'],
    template:
      '<div v-if="modelValue" class="el-dialog-stub"><div class="el-dialog-title">{{ title }}</div><slot /><slot name="footer" /></div>',
  },
  'el-form': {
    name: 'ElFormStub',
    template: '<form class="el-form-stub"><slot /></form>',
  },
  'el-form-item': {
    name: 'ElFormItemStub',
    template: '<div class="el-form-item-stub"><slot /></div>',
  },
  'el-input': {
    name: 'ElInputStub',
    props: ['modelValue', 'type', 'placeholder', 'disabled', 'autofocus', 'showPassword'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-stub" :type="type" :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

const TOKEN_KEY = 'dc_token'

function makeResponse(status, body) {
  const headers = new Headers()
  return {
    ok: status >= 200 && status < 300,
    status,
    headers,
    json: async () => body,
    text: async () => JSON.stringify(body),
  }
}

function stubFetch(handlers) {
  const fetchMock = vi.fn(async (url) => {
    const handler = handlers[url]
    if (!handler) return makeResponse(404, { detail: 'not found' })
    return typeof handler === 'function' ? handler() : makeResponse(200, handler)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function mountApp() {
  const App = (await import('../App.vue')).default
  const wrapper = mount(App, {
    global: {
      stubs: {
        ConfigSidebar: { template: '<div class="stub-config-sidebar" />' },
        CompareForm: { template: '<div class="stub-compare-form" />' },
        ProgressPanel: { template: '<div class="stub-progress-panel" />' },
        ActionBar: { template: '<div class="stub-action-bar" />' },
        NewConfigDialog: true,
        AdvancedSettingsDialog: true,
        ...elStubs,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('App.vue 登录守卫', () => {
  let fetchMock

  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
    fetchMock = stubFetch({
      '/api/auth/me': () => makeResponse(200, { username: 'admin', is_admin: true }),
      '/api/users': () =>
        makeResponse(200, [{ id: 1, username: 'admin', is_admin: true }]),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('空 localStorage：渲染登录页，不渲染主界面，不发任何请求', async () => {
    const wrapper = await mountApp()
    expect(wrapper.find('.login-card').exists()).toBe(true)
    expect(wrapper.find('.app-header').exists()).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('有效 token 且非管理员：渲染比对主界面，不渲染用户管理界面', async () => {
    localStorage.setItem(TOKEN_KEY, 'token-non-admin')
    fetchMock = stubFetch({
      '/api/auth/me': () => makeResponse(200, { username: 'bob', is_admin: false }),
    })
    const wrapper = await mountApp()
    expect(wrapper.find('.app-header').exists()).toBe(true)
    expect(wrapper.find('.login-card').exists()).toBe(false)
    expect(wrapper.find('.app-main').exists()).toBe(true)
    expect(wrapper.find('.app-admin').exists()).toBe(false)
    expect(wrapper.find('[aria-label="用户管理"]').exists()).toBe(false)
  })

  it('有效 token 且是管理员：直接渲染用户管理界面，不渲染比对主界面', async () => {
    localStorage.setItem(TOKEN_KEY, 'token-admin')
    const wrapper = await mountApp()
    expect(wrapper.find('.app-header').exists()).toBe(true)
    expect(wrapper.find('.app-admin').exists()).toBe(true)
    expect(wrapper.find('.app-main').exists()).toBe(false)
    expect(wrapper.find('[aria-label="用户管理"]').exists()).toBe(false)
  })

  it('有 token 但 /auth/me 返回 401：清会话并回到登录页', async () => {
    localStorage.setItem(TOKEN_KEY, 'token-expired')
    fetchMock = stubFetch({
      '/api/auth/me': () => makeResponse(401, { detail: '未授权' }),
    })
    const wrapper = await mountApp()
    expect(wrapper.find('.login-card').exists()).toBe(true)
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})
