import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from './useApi'
import { config } from './useConfig'

const oldSheets = ref([])
const newSheets = ref([])
const scanning = ref(false)
const scanError = ref(null)
const activeScans = ref(0)

const allSheets = computed(() =>
  [...new Set([...oldSheets.value, ...newSheets.value])]
)

function resetSheets(kind = null) {
  if (!kind) {
    oldSheets.value = []
    newSheets.value = []
    config.old_file_sheets = []
    config.new_file_sheets = []
  } else if (kind === 'old') {
    oldSheets.value = []
    config.old_file_sheets = []
  } else {
    newSheets.value = []
    config.new_file_sheets = []
  }
  scanError.value = null
}

function restoreSheetsFromConfig() {
  oldSheets.value = [...(config.old_file_sheets ?? [])]
  newSheets.value = [...(config.new_file_sheets ?? [])]
}

async function scanFile(uploadId, kind) {
  if (!uploadId) return
  activeScans.value += 1
  scanning.value = true
  scanError.value = null
  try {
    const body = await api.get(`/sheets?upload_id=${encodeURIComponent(uploadId)}`)
    if (kind === 'old') {
      oldSheets.value = body.sheets || []
      config.old_file_sheets = [...oldSheets.value]
    } else {
      newSheets.value = body.sheets || []
      config.new_file_sheets = [...newSheets.value]
    }
    ElMessage.success(
      `已扫描${kind === 'old' ? '旧版本' : '新版本'}文件：${(body.sheets || []).length} 个表单`
    )
  } catch (err) {
    scanError.value = err
    ElMessage.error(`扫描文件失败：${err.message}`)
  } finally {
    activeScans.value -= 1
    scanning.value = activeScans.value > 0
  }
}

export { resetSheets, restoreSheetsFromConfig }
export function useSheets() {
  return {
    oldSheets,
    newSheets,
    allSheets,
    scanning,
    scanError,
    scanFile,
    resetSheets,
    restoreSheetsFromConfig,
  }
}
