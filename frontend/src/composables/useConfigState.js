import { computed, ref } from 'vue'
import {
  buildParameters,
  config,
  emptyConfig,
  loadConfig,
  saveCurrentConfig,
} from './useConfig'

export const LAST_CONFIG_STORAGE_KEY = 'dc_last_config'

function lastConfigStorageKey() {
  const username = localStorage.getItem('dc_username') || 'anonymous'
  return `${LAST_CONFIG_STORAGE_KEY}:${username}`
}
export const currentName = ref('')
export const savedSnapshot = ref(null)
export const builtinTemplates = ref([])
export const newConfigVisible = ref(false)

let newConfigResolver = null
let dialogBackup = null

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function rememberConfig(name) {
  currentName.value = name
  localStorage.setItem(lastConfigStorageKey(), name)
}

export const isDirty = computed(() => {
  if (!savedSnapshot.value) return true
  return JSON.stringify(buildParameters()) !== JSON.stringify(savedSnapshot.value)
})

export async function selectConfig(name) {
  await loadConfig(name)
  config.config_name = name
  currentName.value = name
  savedSnapshot.value = clone(buildParameters())
  rememberConfig(name)
}

export async function saveConfig(name = currentName.value) {
  const trimmedName = name.trim()
  if (!trimmedName) throw new Error('配置名称不能为空')
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
  currentName.value = ''
  savedSnapshot.value = null
  localStorage.removeItem(lastConfigStorageKey())
  Object.assign(config, emptyConfig())
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

export function openNewConfigDialog() {
  if (newConfigResolver) newConfigResolver(null)
  dialogBackup = clone(config)
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
  if (dialogBackup) Object.assign(config, dialogBackup)
  dialogBackup = null
  const resolver = newConfigResolver
  newConfigResolver = null
  newConfigVisible.value = false
  resolver?.(null)
}
