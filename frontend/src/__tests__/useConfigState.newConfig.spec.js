/**
 * 新建项目空白语义回归测试。
 *
 * 背景：createNew 原先只弹窗不清空，把上一个项目的文件与参数原样
 * 另存为新名字。修复后 blank 模式打开弹窗时重置 config 与扫描结果，
 * 取消时完整还原；保存/自动保存路径（无参调用）不受影响。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { config, emptyConfig } from '../composables/useConfig.js'
import {
  cancelNewConfigDialog,
  openNewConfigDialog,
  resolveNewConfigDialog,
} from '../composables/useConfigState.js'
import { useSheets } from '../composables/useSheets.js'

const { oldSheets, newSheets } = useSheets()

vi.mock('../composables/useApi', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    download: vi.fn(),
  },
}))

describe('new config dialog blank semantics', () => {
  beforeEach(() => {
    localStorage.clear()
    // 恢复默认状态
    Object.assign(config, emptyConfig())
    oldSheets.value = []
    newSheets.value = []
  })

  function fillConfig() {
    config.old_file_upload_id = 'up-old'
    config.new_file_upload_id = 'up-new'
    config.old_file_path = 'old.xlsx'
    config.new_file_path = 'new.xlsx'
    config.old_file_sheets = ['A', 'B']
    config.new_file_sheets = ['A', 'C']
    config.anchor_row_num = 3
    config.common_cols = ['X']
    oldSheets.value = ['A', 'B']
    newSheets.value = ['A', 'C']
  }

  it('blank: clears files, parameters and sheet scans while dialog is open', async () => {
    fillConfig()
    const p = openNewConfigDialog({ blank: true })
    await nextTick()
    expect(config.old_file_upload_id).toBeNull()
    expect(config.new_file_upload_id).toBeNull()
    expect(config.old_file_path).toBe('')
    expect(config.new_file_path).toBe('')
    expect(config.anchor_row_num).toBe(1)
    expect(config.common_cols).toEqual([])
    expect(oldSheets.value).toEqual([])
    expect(newSheets.value).toEqual([])
    // 关掉弹窗（确认路径，避免悬挂 resolver）
    resolveNewConfigDialog('新项目')
    await p
  })

  it('blank: cancel restores everything including sheet scans', async () => {
    fillConfig()
    const p = openNewConfigDialog({ blank: true })
    await nextTick()
    expect(config.old_file_upload_id).toBeNull()
    cancelNewConfigDialog()
    await nextTick()
    expect(await p).toBeNull()
    expect(config.old_file_upload_id).toBe('up-old')
    expect(config.new_file_upload_id).toBe('up-new')
    expect(config.old_file_path).toBe('old.xlsx')
    expect(config.new_file_path).toBe('new.xlsx')
    expect(config.anchor_row_num).toBe(3)
    expect(config.common_cols).toEqual(['X'])
    expect(oldSheets.value).toEqual(['A', 'B'])
    expect(newSheets.value).toEqual(['A', 'C'])
  })

  it('plain open (no blank) keeps the current config', async () => {
    fillConfig()
    const p = openNewConfigDialog()
    await nextTick()
    expect(config.old_file_upload_id).toBe('up-old')
    expect(config.anchor_row_num).toBe(3)
    expect(oldSheets.value).toEqual(['A', 'B'])
    resolveNewConfigDialog('临时项目')
    await p
  })
})
