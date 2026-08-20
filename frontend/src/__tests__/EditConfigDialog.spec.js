import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { config } from '../composables/useConfig.js'
import {
  cancelEditConfigDialog,
  editConfigVisible,
  editConfigName,
  openEditConfigDialog,
  resolveEditConfigDialog,
} from '../composables/useConfigState.js'

describe('edit config dialog state', () => {
  it('open prefills name, resolve returns trimmed new name and closes', async () => {
    const p = openEditConfigDialog('旧名')
    await nextTick()
    expect(editConfigVisible.value).toBe(true)
    expect(editConfigName.value).toBe('旧名')
    resolveEditConfigDialog('  新名  ')
    await nextTick()
    expect(await p).toBe('新名')
    expect(editConfigVisible.value).toBe(false)
  })

  it('cancel restores config backup', async () => {
    config.anchor_row_num = 5
    config.common_cols = ['X']
    const p = openEditConfigDialog('某项目')
    config.anchor_row_num = 9
    config.common_cols = ['Y']
    cancelEditConfigDialog()
    await nextTick()
    expect(await p).toBeNull()
    expect(config.anchor_row_num).toBe(5)
    expect(config.common_cols).toEqual(['X'])
  })

  it('new and edit dialogs share visibility composably', async () => {
    // 打开编辑时 newConfigVisible 仍为 false，两个弹窗互不干扰
    const { newConfigVisible, openNewConfigDialog, cancelNewConfigDialog } = await import(
      '../composables/useConfigState.js'
    )
    const p = openEditConfigDialog('A')
    expect(newConfigVisible.value).toBe(false)
    cancelEditConfigDialog()
    await nextTick()
    expect(await p).toBeNull()
    const p2 = openNewConfigDialog()
    expect(editConfigVisible.value).toBe(false)
    cancelNewConfigDialog()
    await nextTick()
    expect(await p2).toBeNull()
  })
})
