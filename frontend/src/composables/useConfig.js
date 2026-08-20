import { reactive } from 'vue'
import { api } from './useApi.js'

export const DEFAULT_COLORS = {
  highlight_fill: '#FFE5E5',
  missing_sheet_tab: '#DC143C',
  new_sheet_tab: '#00FF00',
}

export const DEFAULT_WORKERS = 4

export function emptyConfig() {
  return {
    old_file_path: '',
    new_file_path: '',
    output_directory: '',
    old_file_upload_id: null,
    new_file_upload_id: null,
    old_file_sheets: [],
    new_file_sheets: [],
    config_name: 'web',
    anchor_row_num: 1,
    header_row_num: 1,
    max_workers: DEFAULT_WORKERS,
    merge_deleted_data: true,
    common_cols: [],
    exclude_sheets: [],
    default_keys: [],
    sheet_key_map: {},
    include_sheets: [],
    ignore_cols: [],
    sheet_ignore_cols: {},
    sheet_order: [],
    colors: { ...DEFAULT_COLORS },
  }
}

export const config = reactive(emptyConfig())

function cloneValue(value) {
  if (value === undefined) return value
  return JSON.parse(JSON.stringify(value))
}

const FILE_STATE_KEYS = new Set([
  'old_file_path',
  'new_file_path',
  'old_file_upload_id',
  'new_file_upload_id',
  'old_file_sheets',
  'new_file_sheets',
])

export function applyDocument(doc, options = {}) {
  const preserveFiles = options.preserveFiles === true
  const defaults = emptyConfig()
  for (const key of Object.keys(defaults)) {
    if (key === 'output_directory') continue
    if (preserveFiles && FILE_STATE_KEYS.has(key)) continue
    if (FILE_STATE_KEYS.has(key)) {
      config[key] = key in doc ? cloneValue(doc[key]) : defaults[key]
      continue
    }
    if (key in doc) {
      config[key] = cloneValue(doc[key])
    }
  }
}

// 保存配置预设用：记住文件名与上传 id，输出目录仍由当前会话决定。
export function buildParameters() {
  const document = {
    old_file_path: config.old_file_path,
    new_file_path: config.new_file_path,
    output_directory: '',
    config_name: config.config_name,
    anchor_row_num: config.anchor_row_num,
    header_row_num: config.header_row_num,
    max_workers: config.max_workers || null,
    merge_deleted_data: config.merge_deleted_data,
    common_cols: config.common_cols,
    exclude_sheets: config.exclude_sheets,
    default_keys: config.default_keys,
    sheet_key_map: config.sheet_key_map,
    include_sheets: config.include_sheets,
    ignore_cols: config.ignore_cols,
    sheet_ignore_cols: config.sheet_ignore_cols,
    sheet_order: config.sheet_order,
    colors: { ...config.colors },
  }
  if (config.old_file_upload_id) {
    document.old_file_upload_id = config.old_file_upload_id
  }
  if (config.new_file_upload_id) {
    document.new_file_upload_id = config.new_file_upload_id
  }
  document.old_file_sheets = config.old_file_sheets
  document.new_file_sheets = config.new_file_sheets
  return document
}

// 提交任务用：附带会话内上传文件 id；路径强制留空，
// 避免后端 _resolve_job_input 因「路径 + 上传 id 同时提供」返回 400
export function buildJobPayload() {
  const parameters = Object.fromEntries(
    Object.entries(buildParameters()).filter(
      ([key]) =>
        key !== 'old_file_path' &&
        key !== 'new_file_path' &&
        key !== 'old_file_sheets' &&
        key !== 'new_file_sheets'
    )
  )
  return {
    ...parameters,
    old_file_upload_id: config.old_file_upload_id,
    new_file_upload_id: config.new_file_upload_id,
  }
}

export async function saveCurrentConfig(name) {
  const document = buildParameters()
  await api.put(`/configs/${encodeURIComponent(name)}`, document)
}

export async function loadConfig(name) {
  const doc = await api.get(`/configs/${encodeURIComponent(name)}`)
  applyDocument(doc)
}

export async function listConfigs() {
  return api.get('/configs')
}

export async function deleteConfig(name) {
  return api.del(`/configs/${encodeURIComponent(name)}`)
}

export async function copyConfig(name, newName) {
  return api.post(`/configs/${encodeURIComponent(name)}/copy`, { new_name: newName })
}
