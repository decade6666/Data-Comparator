import { computed, ref } from 'vue'
import {
  buildParameters,
  config,
  emptyConfig,
  loadConfig,
  saveCurrentConfig,
} from './useConfig.js'
import { resetSheets, restoreSheetsFromConfig } from './useSheets.js'
import { activateJob, adoptJob, dropJob } from './useJob.js'
import { api } from './useApi.js'

export const LAST_CONFIG_STORAGE_KEY = 'dc_last_config'

function lastConfigStorageKey() {
  const username = localStorage.getItem('dc_username') || 'anonymous'
  return `${LAST_CONFIG_STORAGE_KEY}:${username}`
}
export const currentName = ref('')
export const savedSnapshot = ref(null)
export const builtinTemplates = ref([])
export const newConfigVisible = ref(false)
export const editConfigVisible = ref(false)
export const editConfigName = ref('')

let newConfigResolver = null
let dialogBackup = null
let editConfigResolver = null
let editDialogBackup = null

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function rememberConfig(name) {
  currentName.value = name
  localStorage.setItem(lastConfigStorageKey(), name)
  activateJob(name)
}

export const isDirty = computed(() => {
  if (!savedSnapshot.value) return true
  return JSON.stringify(buildParameters()) !== JSON.stringify(savedSnapshot.value)
})

export async function selectConfig(name) {
  await loadConfig(name)
  config.config_name = name
  restoreSheetsFromConfig()
  currentName.value = name
  savedSnapshot.value = clone(buildParameters())
  rememberConfig(name)
}

export async function saveConfig(name = currentName.value) {
  const trimmedName = name.trim()
  if (!trimmedName) throw new Error('项目名称不能为空')
  config.config_name = trimmedName
  await saveCurrentConfig(trimmedName)
  rememberConfig(trimmedName)
  savedSnapshot.value = clone(buildParameters())
  return trimmedName
}

export async function saveConfigWithPrompt() {
  const name = currentName.value || (await openNewConfigDialog())
  if (!name) return null
  return saveConfig(name)
}

export async function autoSaveBeforeStart() {
  return saveConfigWithPrompt()
}

export function revertConfig() {
  const nextConfig = savedSnapshot.value
    ? clone(savedSnapshot.value)
    : emptyConfig()
  Object.assign(config, nextConfig)
}

export function clearSelectedConfig() {
  const previousName = currentName.value
  currentName.value = ''
  savedSnapshot.value = null
  localStorage.removeItem(lastConfigStorageKey())
  Object.assign(config, emptyConfig())
  resetSheets()
  if (previousName) dropJob(previousName)
  activateJob('')
}

export async function restoreLastConfig(availableNames) {
  const name = localStorage.getItem(lastConfigStorageKey())
  if (!name || !availableNames.includes(name)) {
    if (name) localStorage.removeItem(LAST_CONFIG_STORAGE_KEY)
    return false
  }
  await selectConfig(name)
  return true
}

// 409 恢复第一步：尝试接管后端仍在运行的比对任务。
// 返回 true（已接管并切到任务所属项目）/ 'stale'（占位残留）/
// 'none'（后端无活跃任务）/ 'unavailable'（老后端无此接口，404）。
// 先 selectConfig（内部 rememberConfig → activateJob 设 activeKey）再 adoptJob
// 灌桶；顺序反过来 adoptJob 的内容会被 selectConfig 路径覆盖。
export async function adoptActiveJob(availableNames) {
  let body
  try {
    body = await api.get('/jobs/active')
  } catch (err) {
    // 老后端没有该接口：返回 'unavailable' 交由调用方回落，不当致命错误
    if (err.status === 404) return 'unavailable'
    throw err
  }
  if (!body || !body.active) return 'none'
  if (body.stale) return 'stale'
  const name = body.config_name || ''
  if (name && availableNames.includes(name)) {
    await selectConfig(name)
  } else {
    // 项目已被删除/改名：任务仍恢复到该名称的桶，进度可见。
    activateJob(name)
  }
  adoptJob(name, body)
  return true
}

// 页面重开后接管后端仍在运行的比对任务：
// 返回 true（已接管并切到任务所属项目）/ false（无活跃任务或已回落恢复
// 上次项目）/ 'stale'（占位残留）。
// withConfigFallback：无活跃任务或接口不可用（新前端 + 老后端）时静默回落
// restoreLastConfig；回落一律返回 false，让调用方按「非接管」分支提示。
export async function restoreActiveJob(availableNames, { withConfigFallback = true } = {}) {
  let outcome
  try {
    outcome = await adoptActiveJob(availableNames)
  } catch (err) {
    // adoptActiveJob 已把 /jobs/active 的 404 转 'unavailable'；这里的 404
    // 只可能来自 selectConfig（项目在列表与加载之间被删），同样回落。
    if (withConfigFallback && err.status === 404) {
      await restoreLastConfig(availableNames)
      return false
    }
    throw err
  }
  if (outcome === true || outcome === 'stale') return outcome
  // 'none' / 'unavailable'
  if (withConfigFallback) await restoreLastConfig(availableNames)
  return false
}

export function openNewConfigDialog(options = {}) {
  if (newConfigResolver) newConfigResolver(null)
  dialogBackup = clone(config)
  // blank：新建项目从空白开始（不带入上一个项目的文件与参数）；
  // 保存/自动保存路径调用时无此参数，保留当前内容。
  if (options.blank) {
    Object.assign(config, emptyConfig())
    resetSheets()
  }
  newConfigVisible.value = true
  return new Promise((resolve) => {
    newConfigResolver = resolve
  })
}

export function resolveNewConfigDialog(name) {
  const resolver = newConfigResolver
  newConfigResolver = null
  dialogBackup = null
  newConfigVisible.value = false
  resolver?.(name.trim())
}

export function cancelNewConfigDialog() {
  if (dialogBackup) {
    Object.assign(config, dialogBackup)
    restoreSheetsFromConfig() // config 还原后同步扫描结果
  }
  dialogBackup = null
  const resolver = newConfigResolver
  newConfigResolver = null
  newConfigVisible.value = false
  resolver?.(null)
}

export function openEditConfigDialog(name) {
  if (editConfigResolver) editConfigResolver(null)
  editDialogBackup = clone(config)
  editConfigName.value = name
  editConfigVisible.value = true
  return new Promise((resolve) => {
    editConfigResolver = resolve
  })
}

export function resolveEditConfigDialog(newName) {
  const resolver = editConfigResolver
  editConfigResolver = null
  editDialogBackup = null
  editConfigVisible.value = false
  resolver?.(newName.trim())
}

export function cancelEditConfigDialog() {
  if (editDialogBackup) Object.assign(config, editDialogBackup)
  editDialogBackup = null
  const resolver = editConfigResolver
  editConfigResolver = null
  editConfigVisible.value = false
  resolver?.(null)
}
