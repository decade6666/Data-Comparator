import { reactive } from 'vue'
import { api } from './useApi'

export const DEFAULT_COLORS = {
  highlight_fill: '#FFE5E5',
  missing_sheet_tab: '#DC143C',
  new_sheet_tab: '#00FF00',
}

export const DEFAULT_WORKERS = 4

function emptyConfig() {
  return {
    old_file_path: '',
    new_file_path: '',
    output_directory: '',
    old_file_upload_id: null,
    new_file_upload_id: null,
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

export function applyDocument(doc) {
  for (const key of Object.keys(emptyConfig())) {
    if (key in doc) {
      config[key] = doc[key]
    }
  }
}

export function buildParameters() {
  return {
    old_file_path: config.old_file_path,
    new_file_path: config.new_file_path,
    output_directory: config.output_directory,
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
