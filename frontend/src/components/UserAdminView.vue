<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete,
  DeleteFilled,
  EditPen,
  FolderOpened,
  Key,
  Plus,
  Refresh,
} from '@element-plus/icons-vue'
import { api } from '../composables/useApi'
import { formatBytes } from '../composables/byteSize'
import { confirmDelete, confirmFinalDelete } from '../composables/deleteConfirmation'

const users = ref([])
const loading = ref(false)
const showUserEdit = ref(false)
const userForm = reactive({ id: null, username: '', password: '' })
const showResetPassword = ref(false)
const passwordForm = reactive({ id: null, username: '', password: '' })

// 项目列表（两步式批量操作）
const showConfigList = ref(false)
const configListUser = ref(null)
const configNames = ref([])
const selectedConfigNames = ref([])
const batchMode = ref('copy')
const batchTargetUserId = ref(null)
const configListStep = ref('select')

// 回收站
const showRecycleBin = ref(false)
const recycleItems = ref([])
const loadingRecycle = ref(false)
const restoringItem = ref(null)
const restoreTargetUserId = ref(null)

// 回收站清理策略
const showCleanupPolicy = ref(false)
const loadingPolicy = ref(false)
const previewing = ref(false)
const previewItems = ref([])
const policyBaseline = ref(null)
const policyForm = reactive({
  interval_minutes: 60,
  min_retain_hours: 24,
  age: { enabled: false, value: 30, unit: 'day' },
  size: { enabled: false, value: 500, unit: 'MB' },
  total_estimated_size_bytes: 0,
  recycled_config_count: 0,
})

async function refresh() {
  loading.value = true
  try {
    users.value = await api.get('/users')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loading.value = false
  }
}

function openAddUser() {
  userForm.id = null
  userForm.username = ''
  userForm.password = ''
  showUserEdit.value = true
}

function openRenameUser(user) {
  userForm.id = user.id
  userForm.username = user.username
  userForm.password = ''
  showUserEdit.value = true
}

async function saveUser() {
  if (!userForm.username.trim()) {
    ElMessage.error('用户名不能为空')
    return
  }
  try {
    if (userForm.id) {
      await api.put(`/users/${userForm.id}`, { username: userForm.username.trim() })
      ElMessage.success('用户名已修改')
    } else {
      if (userForm.password.length < 8) {
        ElMessage.error('密码至少 8 位')
        return
      }
      await api.post('/users', {
        username: userForm.username.trim(),
        password: userForm.password,
      })
      ElMessage.success('用户已创建')
    }
    showUserEdit.value = false
    await refresh()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

function openResetPassword(user) {
  passwordForm.id = user.id
  passwordForm.username = user.username
  passwordForm.password = ''
  showResetPassword.value = true
}

async function submitPasswordReset() {
  if (passwordForm.password.length < 8) {
    ElMessage.error('密码至少 8 位')
    return
  }
  try {
    await api.put(`/users/${passwordForm.id}/password`, { password: passwordForm.password })
    ElMessage.success('密码已重置')
    showResetPassword.value = false
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function deleteUser(user) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户 "${user.username}" 吗？该用户的所有项目将进入回收站。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await api.del(`/users/${user.id}`)
    ElMessage.success('用户已删除')
    await refresh()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

// ---- 项目列表批量操作 ----

function resetConfigList() {
  configListUser.value = null
  configNames.value = []
  selectedConfigNames.value = []
  batchMode.value = 'copy'
  batchTargetUserId.value = null
  configListStep.value = 'select'
  showConfigList.value = false
}

async function openConfigList(user) {
  resetConfigList()
  configListUser.value = { id: user.id, username: user.username }
  showConfigList.value = true
  try {
    const body = await api.get(`/admin/users/${user.id}/configs`)
    configNames.value = body.configs || []
  } catch (err) {
    ElMessage.error(err.message)
  }
}

function onConfigSelectionChange(rows) {
  selectedConfigNames.value = rows
}

const canExecuteBatch = computed(() => !!batchTargetUserId.value)
const batchConfirmText = computed(() => {
  if (batchMode.value === 'copy') return '确认复制'
  if (batchMode.value === 'move') return '确认迁移'
  return '确认删除'
})

function startBatchAction(mode) {
  if (!selectedConfigNames.value.length) return
  batchMode.value = mode
  if (mode === 'delete') {
    executeBatchDelete()
    return
  }
  configListStep.value = 'target'
}

function backToConfigSelection() {
  configListStep.value = 'select'
}

function executeBatchAction() {
  if (!canExecuteBatch.value) return
  return batchMode.value === 'copy' ? executeBatchCopy() : executeBatchMove()
}

async function executeBatchCopy() {
  if (!canExecuteBatch.value) return
  try {
    const results = await api.post('/admin/configs/batch-copy', {
      config_names: selectedConfigNames.value,
      source_user_id: configListUser.value.id,
      target_user_id: batchTargetUserId.value,
    })
    const successCount = (results || []).filter((r) => r.status === 'success').length
    ElMessage.success(`成功复制 ${successCount} 个项目`)
    resetConfigList()
    await refresh()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function executeBatchMove() {
  if (!canExecuteBatch.value) return
  try {
    const body = await api.post('/admin/configs/batch-move', {
      config_names: selectedConfigNames.value,
      source_user_id: configListUser.value.id,
      target_user_id: batchTargetUserId.value,
    })
    ElMessage.success(`成功迁移 ${body.moved} 个项目`)
    resetConfigList()
    await refresh()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function executeBatchDelete() {
  if (!selectedConfigNames.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedConfigNames.value.length} 个项目吗？删除后如需恢复，请联系管理员。`,
      '删除项目',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const body = await api.post('/admin/configs/batch-delete', {
      config_names: selectedConfigNames.value,
      user_id: configListUser.value.id,
    })
    ElMessage.success(`已删除 ${body.deleted} 个项目`)
    resetConfigList()
    await refresh()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

// ---- 回收站 ----

async function loadRecycleBin() {
  loadingRecycle.value = true
  try {
    recycleItems.value = await api.get('/admin/recycle-bin')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loadingRecycle.value = false
  }
}

async function openRecycleBin() {
  showRecycleBin.value = true
  await loadRecycleBin()
}

async function restoreConfig(item) {
  try {
    await ElMessageBox.confirm(
      `确定恢复项目 "${item.original_config_name}" 吗？`,
      '恢复项目',
      { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' }
    )
    const ownerExists = users.value.some((u) => u.id === item.original_owner_id)
    if (ownerExists) {
      await api.post(`/admin/recycle-bin/${item.id}/restore`, {})
      ElMessage.success('项目已恢复')
      await loadRecycleBin()
    } else {
      // 孤儿条目：原用户已删除，行内选择目标用户
      restoringItem.value = item.id
      restoreTargetUserId.value = null
    }
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function confirmOrphanRestore() {
  const item = recycleItems.value.find((i) => i.id === restoringItem.value)
  if (!item || !restoreTargetUserId.value) return
  try {
    await api.post(`/admin/recycle-bin/${item.id}/restore`, {
      target_user_id: restoreTargetUserId.value,
    })
    ElMessage.success('项目已恢复')
    restoringItem.value = null
    restoreTargetUserId.value = null
    await loadRecycleBin()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function hardDeleteConfig(item) {
  try {
    await ElMessageBox.confirm(
      `确定彻底删除项目 "${item.original_config_name}" 吗？此操作不可逆！`,
      '彻底删除',
      { type: 'warning', confirmButtonText: '彻底删除', cancelButtonText: '取消' }
    )
    await confirmFinalDelete(ElMessageBox.confirm, {
      actionText: '彻底删除',
      targetText: item.original_config_name,
      confirmButtonText: '确认彻底删除',
    })
    await api.del(`/admin/recycle-bin/${item.id}`)
    ElMessage.success('已彻底删除')
    await loadRecycleBin()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

// ---- 回收站清理策略 ----

function buildPolicyPayload() {
  return {
    interval_minutes: policyForm.interval_minutes,
    min_retain_hours: policyForm.min_retain_hours,
    age: { ...policyForm.age },
    size: { ...policyForm.size },
  }
}

function applyPolicy(payload) {
  policyForm.interval_minutes = payload.interval_minutes ?? 60
  policyForm.min_retain_hours = payload.min_retain_hours ?? 24
  policyForm.age.enabled = Boolean(payload.age?.enabled)
  policyForm.age.value = payload.age?.value ?? 30
  policyForm.age.unit = payload.age?.unit ?? 'day'
  policyForm.size.enabled = Boolean(payload.size?.enabled)
  policyForm.size.value = payload.size?.value ?? 500
  policyForm.size.unit = payload.size?.unit ?? 'MB'
  policyForm.total_estimated_size_bytes = payload.total_estimated_size_bytes ?? 0
  policyForm.recycled_config_count = payload.recycled_config_count ?? 0
  policyBaseline.value = JSON.stringify(buildPolicyPayload())
}

const isPolicyDirty = computed(
  () => policyBaseline.value !== null && policyBaseline.value !== JSON.stringify(buildPolicyPayload())
)

async function loadCleanupPolicy() {
  loadingPolicy.value = true
  try {
    const payload = await api.get('/admin/recycle-bin/cleanup-policy')
    applyPolicy(payload)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loadingPolicy.value = false
  }
}

function openCleanupPolicy() {
  previewItems.value = []
  showCleanupPolicy.value = true
  loadCleanupPolicy()
}

async function saveCleanupPolicy() {
  if (policyForm.age.value < 1 || policyForm.size.value < 1) {
    ElMessage.error('阈值必须大于等于 1')
    return
  }
  if (policyForm.interval_minutes < 1 || policyForm.interval_minutes > 1440) {
    ElMessage.error('巡检间隔必须在 1 到 1440 分钟之间')
    return
  }
  if (policyForm.min_retain_hours < 0) {
    ElMessage.error('最短保留时间不能小于 0')
    return
  }
  const previous = policyBaseline.value ? JSON.parse(policyBaseline.value) : null
  const enablingAge = policyForm.age.enabled && !previous?.age?.enabled
  const enablingSize = policyForm.size.enabled && !previous?.size?.enabled
  try {
    if (enablingAge || enablingSize) {
      await confirmDelete(ElMessageBox.confirm, {
        actionText: '启用自动清理',
        targetText: '当前回收站策略',
        title: '启用自动清理',
        firstConfirmButtonText: '继续启用',
      })
    }
    const saved = await api.put('/admin/recycle-bin/cleanup-policy', buildPolicyPayload())
    applyPolicy(saved)
    ElMessage.success('清理策略已保存')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}

async function previewCleanup() {
  previewing.value = true
  try {
    previewItems.value = await api.post('/admin/recycle-bin/cleanup/preview', {})
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    previewing.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="user-admin-view">
    <div class="workspace-header">
      <div class="workspace-title">用户管理</div>
      <div class="workspace-actions">
        <el-tooltip content="新增用户" placement="top">
          <el-button type="primary" :icon="Plus" aria-label="新增用户" @click="openAddUser" />
        </el-tooltip>
        <el-tooltip content="刷新" placement="top">
          <el-button :icon="Refresh" aria-label="刷新" :loading="loading" @click="refresh" />
        </el-tooltip>
        <el-tooltip content="回收站" placement="top">
          <el-button :icon="DeleteFilled" aria-label="回收站" @click="openRecycleBin" />
        </el-tooltip>
      </div>
    </div>

    <el-table v-loading="loading" :data="users" border stripe size="small">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="用户名" min-width="160">
        <template #default="{ row }">
          <div class="user-name-cell">
            <span>{{ row.username }}</span>
            <el-tag v-if="row.is_admin" size="small" type="danger">管理员</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250">
        <template #default="{ row }">
          <el-tooltip content="改名" placement="top">
            <el-button size="small" link :icon="EditPen" aria-label="改名" @click="openRenameUser(row)" />
          </el-tooltip>
          <el-tooltip content="重置密码" placement="top">
            <el-button size="small" link :icon="Key" aria-label="重置密码" @click="openResetPassword(row)" />
          </el-tooltip>
          <el-tooltip v-if="!row.is_admin" content="项目列表" placement="top">
            <el-button size="small" link :icon="FolderOpened" aria-label="项目列表" @click="openConfigList(row)" />
          </el-tooltip>
          <el-tooltip v-if="!row.is_admin" content="删除" placement="top">
            <el-button size="small" link type="danger" :icon="Delete" aria-label="删除" :disabled="row.is_admin" @click="deleteUser(row)" />
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showUserEdit" :title="userForm.id ? '修改用户名' : '新增用户'" width="400px" append-to-body>
      <el-form label-width="80px" @submit.prevent="saveUser">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" autofocus placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item v-if="!userForm.id" label="初始密码">
          <el-input v-model="userForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserEdit = false">取消</el-button>
        <el-button type="primary" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResetPassword" title="重置密码" width="400px" append-to-body>
      <el-form label-width="80px" @submit.prevent="submitPasswordReset">
        <el-form-item label="用户名">
          <el-input :model-value="passwordForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResetPassword = false">取消</el-button>
        <el-button type="primary" @click="submitPasswordReset">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showConfigList" :title="`项目列表 - ${configListUser?.username || ''}`" width="600px" append-to-body @close="resetConfigList">
      <template v-if="configListStep === 'select'">
        <div class="batch-hint">请先选择要操作的项目，再选择 复制 / 迁移 / 删除。</div>
        <el-table :data="configNames" @selection-change="onConfigSelectionChange" border max-height="320">
          <el-table-column type="selection" width="50" align="center" />
          <el-table-column label="项目名称">
            <template #default="{ row }">{{ row }}</template>
          </el-table-column>
        </el-table>
      </template>
      <div v-else class="batch-target-row">
        <span>选择目标用户：</span>
        <el-select v-model="batchTargetUserId" placeholder="请选择用户">
          <el-option v-for="u in users.filter((item) => item.id !== configListUser?.id)" :key="u.id" :label="u.username" :value="u.id" />
        </el-select>
      </div>
      <template #footer>
        <template v-if="configListStep === 'select'">
          <el-button @click="resetConfigList">取消</el-button>
          <el-button type="primary" :disabled="!selectedConfigNames.length" @click="startBatchAction('copy')">复制</el-button>
          <el-button type="primary" :disabled="!selectedConfigNames.length" @click="startBatchAction('move')">迁移</el-button>
          <el-button type="danger" :disabled="!selectedConfigNames.length" @click="startBatchAction('delete')">删除</el-button>
        </template>
        <template v-else>
          <el-button @click="backToConfigSelection">上一步</el-button>
          <el-button type="primary" :disabled="!canExecuteBatch" @click="executeBatchAction">{{ batchConfirmText }}</el-button>
        </template>
      </template>
    </el-dialog>

    <el-dialog v-model="showRecycleBin" title="项目回收站" width="860px" append-to-body>
      <div class="tab-header">
        <span class="workspace-subtitle">仅显示已软删除项目</span>
        <div class="tab-header-actions">
          <el-button @click="openCleanupPolicy">清理策略</el-button>
          <el-button @click="loadRecycleBin" :loading="loadingRecycle">刷新</el-button>
        </div>
      </div>
      <el-table v-if="recycleItems.length" :data="recycleItems" v-loading="loadingRecycle" border>
        <el-table-column label="项目名称">
          <template #default="{ row }">{{ row.original_config_name }}</template>
        </el-table-column>
        <el-table-column label="原所有者" width="120">
          <template #default="{ row }">{{ row.original_owner_username }}</template>
        </el-table-column>
        <el-table-column label="大小（估算）" width="120">
          <template #default="{ row }">{{ formatBytes(row.estimated_size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="删除时间" width="180">
          <template #default="{ row }">{{ row.deleted_at }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <template v-if="restoringItem === row.id">
              <el-select v-model="restoreTargetUserId" placeholder="选择用户" size="small">
                <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
              </el-select>
              <el-button size="small" type="primary" :disabled="!restoreTargetUserId" @click="confirmOrphanRestore">确认</el-button>
            </template>
            <template v-else>
              <el-button size="small" type="success" @click="restoreConfig(row)">恢复</el-button>
              <el-button size="small" type="danger" @click="hardDeleteConfig(row)">彻底删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!recycleItems.length" class="empty-state" :image-size="52">
        <template #image>
          <el-icon aria-hidden="true"><DeleteFilled /></el-icon>
        </template>
        <template #description>
          <p>回收站空空如也</p>
        </template>
      </el-empty>
    </el-dialog>

    <el-dialog v-model="showCleanupPolicy" title="回收站清理策略" width="520px" append-to-body>
      <div v-loading="loadingPolicy">
        <el-form label-width="120px">
          <el-form-item label="启用过期清理">
            <el-switch v-model="policyForm.age.enabled" />
          </el-form-item>
          <el-form-item label="保留时长">
            <div class="cleanup-inline-row">
              <el-input-number v-model="policyForm.age.value" :min="1" :disabled="!policyForm.age.enabled" />
              <el-select v-model="policyForm.age.unit" :disabled="!policyForm.age.enabled">
                <el-option label="天" value="day" />
                <el-option label="月" value="month" />
                <el-option label="年" value="year" />
              </el-select>
            </div>
            <div class="cleanup-help">月按 30 天、年按 365 天计算。</div>
          </el-form-item>
          <el-form-item label="启用容量清理">
            <el-switch v-model="policyForm.size.enabled" />
          </el-form-item>
          <el-form-item label="容量上限">
            <div class="cleanup-inline-row">
              <el-input-number v-model="policyForm.size.value" :min="1" :disabled="!policyForm.size.enabled" />
              <el-select v-model="policyForm.size.unit" :disabled="!policyForm.size.enabled">
                <el-option label="MB" value="MB" />
                <el-option label="GB" value="GB" />
              </el-select>
            </div>
            <div class="cleanup-help">超出后从最早删除的项目开始逐个彻底删除，直到总量回落到上限以内。大小为估算值。</div>
          </el-form-item>
          <el-form-item label="最短保留时间">
            <div class="cleanup-inline-row">
              <el-input-number v-model="policyForm.min_retain_hours" :min="0" />
              <span class="cleanup-inline-label">小时</span>
            </div>
          </el-form-item>
          <el-form-item label="巡检间隔">
            <div class="cleanup-inline-row">
              <el-input-number v-model="policyForm.interval_minutes" :min="1" :max="1440" />
              <span class="cleanup-inline-label">分钟</span>
            </div>
          </el-form-item>
          <el-form-item label="当前回收站">
            <div class="cleanup-stats-text">
              {{ policyForm.recycled_config_count }} 个项目，约
              {{ formatBytes(policyForm.total_estimated_size_bytes) }}
            </div>
          </el-form-item>
        </el-form>
        <div class="cleanup-preview-actions">
          <el-button @click="previewCleanup" :loading="previewing">预览将删除</el-button>
        </div>
        <el-table v-if="previewItems.length" :data="previewItems" border max-height="240">
          <el-table-column prop="original_config_name" label="项目名称" />
          <el-table-column prop="owner_username" label="所有者" width="100" />
          <el-table-column label="大小（估算）" width="120">
            <template #default="{ row }">{{ formatBytes(row.estimated_size_bytes) }}</template>
          </el-table-column>
          <el-table-column prop="deleted_at" label="删除时间" width="180" />
          <el-table-column label="命中规则" width="120">
            <template #default="{ row }">{{ row.matched_rules.join(', ') }}</template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showCleanupPolicy = false">取消</el-button>
        <el-button type="primary" :disabled="!isPolicyDirty" @click="saveCleanupPolicy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-admin-view { padding: 8px; }
.workspace-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.workspace-title { font-size: 16px; font-weight: 600; color: var(--color-primary-dark); }
.workspace-actions { display: flex; align-items: center; gap: 8px; }
.user-name-cell { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; }
.user-name-cell > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.tab-header-actions { display: flex; align-items: center; gap: 8px; }
.workspace-subtitle { color: var(--color-text-muted); font-size: 13px; }
.batch-hint { color: var(--color-text-muted); font-size: 12px; margin-bottom: 12px; }
.batch-target-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.cleanup-inline-row { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cleanup-inline-label { color: var(--color-text-muted); }
.cleanup-help { margin-top: 6px; color: var(--color-text-muted); font-size: 12px; line-height: 1.5; }
.cleanup-stats-text { color: var(--color-text-secondary); }
.cleanup-preview-actions { display: flex; justify-content: flex-end; margin: 8px 0 12px; }
.empty-state { margin-top: 12px; }
</style>
