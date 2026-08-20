/**
 * UserAdminView 用户管理界面测试（真实挂载，覆盖改名流程）。
 *
 * 改名功能：操作列新增「改名」按钮（EditPen），与「新增用户」共用
 * 新增/改名表单弹窗（userForm.id 为空为新增并显示初始密码输入框，
 * 非空为改名且隐藏初始密码输入框），提交 PUT /api/users/{id}。
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

const USERS = [
  { id: 1, username: 'admin', is_admin: true, is_active: true },
  { id: 2, username: 'bob', is_admin: false, is_active: true },
]

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

async function mountView() {
  const UserAdminView = (await import('../components/UserAdminView.vue')).default
  const wrapper = mount(UserAdminView, { global: { stubs: elStubs } })
  await flushPromises()
  return wrapper
}

describe('UserAdminView 用户管理', () => {
  let fetchMock

  beforeEach(() => {
    vi.resetModules()
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('渲染用户列表：显示管理员标签与普通用户，操作列含改名/重置密码/配置列表/删除', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('bob')
    // 改名/重置密码对每个用户都有；配置列表/删除仅普通用户可见（admin 行不渲染）
    expect(wrapper.findAll('[aria-label="改名"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="重置密码"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="配置列表"]')).toHaveLength(1)
    expect(wrapper.findAll('[aria-label="删除"]')).toHaveLength(1)
    expect(wrapper.find('[aria-label="回收站"]').exists()).toBe(true)
  })

  it('点击改名：弹窗预填用户名，确定后提交 PUT /users/{id}', async () => {
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
      '/api/users/2': () => makeResponse(204, null),
    })
    const wrapper = await mountView()

    await wrapper.findAll('[aria-label="改名"]')[1].trigger('click')
    await flushPromises()

    const dialog = wrapper.find('.el-dialog-stub')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('修改用户名')
    const input = dialog.find('input')
    expect(input.element.value).toBe('bob')

    await input.setValue('bob2')
    const buttons = dialog.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/users/2',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify({ username: 'bob2' }) })
    )
  })

  it('新增用户弹窗有初始密码输入框；改名弹窗没有', async () => {
    const wrapper = await mountView()

    await wrapper.find('[aria-label="新增用户"]').trigger('click')
    await flushPromises()
    let dialog = wrapper.find('.el-dialog-stub')
    expect(dialog.text()).toContain('新增用户')
    expect(dialog.find('input[type="password"]').exists()).toBe(true)

    // 取消关闭新增弹窗
    await dialog.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.el-dialog-stub').exists()).toBe(false)

    // 打开改名弹窗：v-if="!userForm.id" 生效，无初始密码输入框
    await wrapper.findAll('[aria-label="改名"]')[1].trigger('click')
    await flushPromises()
    dialog = wrapper.find('.el-dialog-stub')
    expect(dialog.text()).toContain('修改用户名')
    expect(dialog.find('input[type="password"]').exists()).toBe(false)
  })
})
