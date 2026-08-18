<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, Document, Back, Refresh } from '@element-plus/icons-vue'
import { api } from '../composables/useApi'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  browseType: { type: String, default: 'all' },
})

const emit = defineEmits(['update:modelValue', 'select'])

const currentPath = ref('')
const parentPath = ref(null)
const entries = ref([])
const loading = ref(false)

async function load(path) {
  loading.value = true
  try {
    const body = await api.get(`/browse?path=${encodeURIComponent(path)}`)
    currentPath.value = body.current_path
    parentPath.value = body.parent_path
    entries.value = body.entries
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loading.value = false
  }
}

function open() {
  if (!currentPath.value) {
    load('/')
  } else {
    load(currentPath.value)
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) open()
  }
)

function selectEntry(entry) {
  if (entry.is_directory) {
    load(entry.path)
  } else {
    emit('select', entry.path)
    emit('update:modelValue', false)
  }
}

function goParent() {
  if (parentPath.value) load(parentPath.value)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="浏览服务器目录"
    width="640px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="browse-toolbar">
      <el-button size="small" :icon="Back" :disabled="!parentPath" @click="goParent">
        上级
      </el-button>
      <el-button size="small" :icon="Refresh" @click="open">刷新</el-button>
      <span class="browse-path">{{ currentPath || '加载中…' }}</span>
    </div>
    <div v-loading="loading" class="browse-list">
      <div
        v-for="entry in entries"
        :key="entry.path"
        class="browse-entry"
        @click="selectEntry(entry)"
        @dblclick="entry.is_directory && load(entry.path)"
      >
        <el-icon :size="16">
          <Folder v-if="entry.is_directory" />
          <Document v-else />
        </el-icon>
        <span class="browse-name">{{ entry.name }}</span>
        <span v-if="!entry.is_directory" class="browse-size">
          {{ entry.size != null ? entry.size + ' B' : '' }}
        </span>
      </div>
      <div v-if="!entries.length && !loading" class="browse-empty">（空目录）</div>
    </div>
  </el-dialog>
</template>

<style scoped>
.browse-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.browse-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
  font-size: var(--font-xs);
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.browse-list {
  max-height: 380px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.browse-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  color: var(--color-text-primary);
  transition: background var(--transition-fast);
}

.browse-entry:hover {
  background: var(--color-bg-hover);
}

.browse-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.browse-size {
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}

.browse-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-text-muted);
}
</style>
