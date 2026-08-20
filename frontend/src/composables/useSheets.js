import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from './useApi'

const oldSheets = ref([])
const newSheets = ref([])
const scanning = ref(false)
const completed = ref({ old: false, new: false })
const scanError = ref(null)
const activeScans = ref(0)

const allSheets = computed(() =>
  [...new Set([...oldSheets.value, ...newSheets.value])]
)
const scanProgress = computed(
  () => (completed.value.old ? 5 : 0) + (completed.value.new ? 5 : 0)
)

function resetSheets(kind = null) {
  if (!kind) {
    oldSheets.value = []
    newSheets.value = []
    completed.value = { old: false, new: false }
  } else if (kind === 'old') {
    oldSheets.value = []
    completed.value = { ...completed.value, old: false }
  } else {
    newSheets.value = []
    completed.value = { ...completed.value, new: false }
  }
  scanError.value = null
}

async function scanFile(uploadId, kind) {
  if (!uploadId) return
  completed.value = { ...completed.value, [kind]: false }
  activeScans.value += 1
  scanning.value = true
  scanError.value = null
  try {
    const body = await api.get(`/sheets?upload_id=${encodeURIComponent(uploadId)}`)
    if (kind === 'old') oldSheets.value = body.sheets || []
    else newSheets.value = body.sheets || []
    completed.value = { ...completed.value, [kind]: true }
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

export function useSheets() {
  return {
    oldSheets,
    newSheets,
    allSheets,
    scanning,
    scanProgress,
    scanError,
    scanFile,
    resetSheets,
  }
}
