/**
 * UserAdminView 回收站/配置操作/用户删除测试。
 *
 * 覆盖：删除用户（软删提示 → DELETE /api/users/{id}）、配置列表批量复制
 * （两步式：勾选 → 选目标用户 → POST /api/admin/configs/batch-copy）、
 * 回收站列表与彻底删除（两级确认 → DELETE /api/admin/recycle-bin/{id}）、
 * 清理策略加载/保存（PUT /api/admin/recycle-bin/cleanup-policy）。
 *
 * elStubs 在 UserAdminView.spec.js 基础上补充：
 * el-table 支持 type="selection" 列（渲染复选框并发出 selection-change）、
 * el-select/el-option、el-switch、el-input-number、el-empty，
 * el-form-item 渲染 label 以便按文案定位表单项。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

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
    emits: ['selection-change'],
    setup(props, { slots, emit }) {
      const selected = new Set()
      return () => {
        const columns = (slots.default ? slots.default() : []).filter(Boolean)
        return h(
          'div',
          { class: 'el-table-stub' },
          props.data.flatMap((row) =>
            columns.map((col) => {
              if ((col.props || {}).type === 'selection') {
                return h('input', {
                  class: 'el-table-selection-checkbox',
                  type: 'checkbox',
                  checked: selected.has(row),
                  onChange: (e) => {
                    if (e.target.checked) selected.add(row)
                    else selected.delete(row)
                    emit('selection-change', props.data.filter((r) => selected.has(r)))
                  },
                })
              }
              return h(col.type, { ...(col.props || {}), row }, col.children || null)
            })
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
    props: ['label'],
    template:
      '<div class="el-form-item-stub"><span class="el-form-item-label">{{ label }}</span><slot /></div>',
  },
  'el-input': {
    name: 'ElInputStub',
    props: ['modelValue', 'type', 'placeholder', 'disabled', 'autofocus', 'showPassword'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-stub" :type="type" :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-select': {
    name: 'ElSelectStub',
    props: ['modelValue', 'placeholder', 'disabled', 'size'],
    emits: ['update:modelValue'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'select',
          {
            class: 'el-select-stub',
            value: props.modelValue ?? '',
            disabled: Boolean(props.disabled),
            onChange: (e) => emit('update:modelValue', Number(e.target.value)),
          },
          slots.default ? slots.default() : []
        )
    },
  },
  'el-option': {
    name: 'ElOptionStub',
    props: ['label', 'value'],
    template: '<option class="el-option-stub" :value="value">{{ label }}</option>',
  },
  'el-switch': {
    name: 'ElSwitchStub',
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<button type="button" class="el-switch-stub" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue ? "on" : "off" }}</button>',
  },
  'el-input-number': {
    name: 'ElInputNumberStub',
    props: ['modelValue', 'min', 'max', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-number-stub" type="number" :min="min" :max="max" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
  'el-empty': {
    name: 'ElEmptyStub',
    template: '<div class="el-empty-stub"><slot /></div>',
  },
  'el-checkbox': {
    name: 'ElCheckboxStub',
    props: ['modelValue', 'label', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<label class="el-checkbox-stub"><input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.checked)" /><span>{{ label }}</span></label>',
  },
  'el-checkbox-group': {
    name: 'ElCheckboxGroupStub',
    template: '<div class="el-checkbox-group-stub"><slot /></div>',
  },
}

const USERS = [
  { id: 1, username: 'admin', is_admin: true, is_active: true },
  { id: 2, username: 'bob', is_admin: false, is_active: true },
]

const RECYCLE_ITEMS = [
  {
    id: 1,
    original_owner_id: 2,
    original_owner_username: 'bob',
    original_config_name: 'cfg-recycled',
    estimated_size_bytes: 2048,
    deleted_at: '2026-08-19T10:00:00',
    deleted_by_user_deletion: false,
  },
]

const POLICY = {
  interval_minutes: 60,
  min_retain_hours: 24,
  age: { enabled: false, value: 30, unit: 'day' },
  size: { enabled: false, value: 500, unit: 'MB' },
  total_estimated_size_bytes: 2048,
  recycled_config_count: 1,
}

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

function findDialog(wrapper, titlePart) {
  return wrapper
    .findAll('.el-dialog-stub')
    .find((d) => d.text().includes(titlePart))
}

describe('UserAdminView 回收站与配置操作', () => {
  let fetchMock

  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('渲染用户列表：改名/重置密码/配置列表/删除按钮齐全，admin 行无配置列表/删除', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('bob')
    expect(wrapper.findAll('[aria-label="改名"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="重置密码"]')).toHaveLength(2)
    // 配置列表/删除仅普通用户行渲染（admin 行不存在）
    expect(wrapper.findAll('[aria-label="配置列表"]')).toHaveLength(1)
    expect(wrapper.findAll('[aria-label="删除"]')).toHaveLength(1)
    expect(wrapper.find('[aria-label="回收站"]').exists()).toBe(true)
  })

  it('删除用户：确认后调用 DELETE /api/users/{id}', async () => {
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
      '/api/users/2': () => makeResponse(204, null),
    })
    const wrapper = await mountView()

    await wrapper.find('[aria-label="删除"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '确定删除用户 "bob" 吗？该用户的所有配置将进入回收站。',
      '删除用户',
      expect.objectContaining({ type: 'warning' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/users/2',
      expect.objectContaining({ method: 'DELETE' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('用户已删除')
  })

  it('配置列表：勾选配置 → 复制 → 选择目标用户 → POST /api/admin/configs/batch-copy', async () => {
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
      '/api/admin/users/2/configs': () =>
        makeResponse(200, { configs: ['cfg1', 'cfg2'] }),
      '/api/admin/configs/batch-copy': () =>
        makeResponse(200, [{ config_name: 'cfg1', new_name: 'cfg1', status: 'success' }]),
    })
    const wrapper = await mountView()

    await wrapper.find('[aria-label="配置列表"]').trigger('click')
    await flushPromises()

    const configDialog = findDialog(wrapper, '配置列表')
    expect(configDialog).toBeTruthy()
    expect(configDialog.text()).toContain('cfg1')
    expect(configDialog.text()).toContain('cfg2')

    // 勾选第一个配置（el-table selection 列）
    const checkboxes = wrapper.findAll('.el-table-selection-checkbox')
    expect(checkboxes).toHaveLength(2)
    await checkboxes[0].setValue(true)
    await flushPromises()

    // 复制按钮无选中时禁用，选中后可点
    const copyButton = configDialog.findAll('button').find((b) => b.text() === '复制')
    await copyButton.trigger('click')
    await flushPromises()

    // 第二步：选择目标用户（排除源用户 bob，仅剩 admin id=1）
    const select = configDialog.find('.el-select-stub')
    expect(select.exists()).toBe(true)
    await select.setValue('1')
    await flushPromises()

    const confirmButton = configDialog.findAll('button').find((b) => b.text() === '确认复制')
    expect(confirmButton.attributes('disabled')).toBeUndefined()
    await confirmButton.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/configs/batch-copy',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          config_names: ['cfg1'],
          source_user_id: 2,
          target_user_id: 1,
        }),
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('成功复制 1 个配置')
    // 成功后关闭弹窗
    expect(findDialog(wrapper, '配置列表')).toBeUndefined()
  })

  it('回收站：渲染列表（大小格式化）并支持两级确认彻底删除', async () => {
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
      '/api/admin/recycle-bin': () => makeResponse(200, RECYCLE_ITEMS),
      '/api/admin/recycle-bin/1': () => makeResponse(204, null),
    })
    const wrapper = await mountView()

    await wrapper.find('[aria-label="回收站"]').trigger('click')
    await flushPromises()

    const recycleDialog = findDialog(wrapper, '配置回收站')
    expect(recycleDialog).toBeTruthy()
    expect(recycleDialog.text()).toContain('cfg-recycled')
    expect(recycleDialog.text()).toContain('bob')
    expect(recycleDialog.text()).toContain('2.0 KB')
    expect(recycleDialog.text()).toContain('2026-08-19T10:00:00')

    const deleteButton = recycleDialog
      .findAll('button')
      .find((b) => b.text() === '彻底删除')
    await deleteButton.trigger('click')
    await flushPromises()

    // 两级确认各调用一次 ElMessageBox.confirm
    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/recycle-bin/1',
      expect.objectContaining({ method: 'DELETE' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除')
  })

  it('清理策略：打开加载表单，修改后可保存，PUT body 正确', async () => {
    fetchMock = stubFetch({
      '/api/users': () => makeResponse(200, USERS),
      '/api/admin/recycle-bin': () => makeResponse(200, RECYCLE_ITEMS),
      '/api/admin/recycle-bin/cleanup-policy': () => makeResponse(200, POLICY),
    })
    const wrapper = await mountView()

    await wrapper.find('[aria-label="回收站"]').trigger('click')
    await flushPromises()

    const recycleDialog = findDialog(wrapper, '配置回收站')
    const policyButton = recycleDialog
      .findAll('button')
      .find((b) => b.text() === '清理策略')
    await policyButton.trigger('click')
    await flushPromises()

    const policyDialog = findDialog(wrapper, '回收站清理策略')
    expect(policyDialog).toBeTruthy()
    expect(policyDialog.text()).toContain('1 个配置')
    expect(policyDialog.text()).toContain('2.0 KB')

    // 表单已填充：巡检间隔初始 60，保存按钮初始禁用
    const intervalItem = policyDialog
      .findAll('.el-form-item-stub')
      .find((i) => i.text().includes('巡检间隔'))
    const intervalInput = intervalItem.find('.el-input-number-stub')
    expect(intervalInput.element.value).toBe('60')

    let saveButton = policyDialog.findAll('button').find((b) => b.text() === '保存')
    expect(saveButton.attributes('disabled')).toBeDefined()

    // 修改巡检间隔后 dirty，保存可点
    await intervalInput.setValue(120)
    await flushPromises()
    saveButton = policyDialog.findAll('button').find((b) => b.text() === '保存')
    expect(saveButton.attributes('disabled')).toBeUndefined()
    await saveButton.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/recycle-bin/cleanup-policy',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          interval_minutes: 120,
          min_retain_hours: 24,
          age: { enabled: false, value: 30, unit: 'day' },
          size: { enabled: false, value: 500, unit: 'MB' },
        }),
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('清理策略已保存')
  })
})
