<script setup>
import { ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Clock, Download, Document, Refresh } from "@element-plus/icons-vue";
import { api } from "../composables/useApi";
import { formatDateTime } from "../composables/formatDateTime";
import HistoryRunDetail from "./HistoryRunDetail.vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  configName: { type: String, default: "" },
});

defineEmits(["update:modelValue"]);

const runs = ref([]);
const loading = ref(false);
const detailCache = ref({});

const STATUS_LABEL = {
  completed: "已完成",
  failed: "失败",
  cancelled: "已停止",
};

async function load() {
  if (!props.configName) return;
  loading.value = true;
  try {
    const rows = await api.get(
      `/history?config_name=${encodeURIComponent(props.configName)}`,
    );
    runs.value = rows;
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      detailCache.value = {};
      runs.value = [];
      load();
    }
  },
  { immediate: true },
);

// 展开时懒加载详情；已缓存的直接复用
async function onExpand(row, expandedRows) {
  if (!expandedRows?.length) return;
  if (detailCache.value[row.id]) return;
  try {
    const detail = await api.get(`/history/${row.id}`);
    detailCache.value[row.id] = detail;
  } catch (err) {
    ElMessage.error(err.message);
  }
}

function statusTagType(status) {
  return (
    {
      completed: "success",
      failed: "danger",
      cancelled: "info",
    }[status] || "info"
  );
}

async function downloadReport(row) {
  try {
    await api.download(
      `/history/${row.id}/report`,
      row.report_filename || "比对报告.xlsx",
    );
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function downloadLog(row) {
  try {
    await api.download(
      `/history/${row.id}/log`,
      row.log_filename || "比对日志.txt",
    );
  } catch (err) {
    ElMessage.error(err.message);
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="历史记录"
    width="900px"
    append-to-body
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="tab-header">
      <span v-if="configName" class="dialog-subtitle"
        >当前项目「{{ configName }}」的比对记录</span
      >
      <span v-else class="dialog-subtitle">请先选择项目</span>
      <div class="tab-header-actions">
        <el-button
          :icon="Refresh"
          :loading="loading"
          :disabled="!configName"
          @click="load"
          >刷新</el-button
        >
      </div>
    </div>

    <el-table
      v-if="runs.length"
      :data="runs"
      v-loading="loading"
      border
      row-key="id"
      @expand-change="onExpand"
    >
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <HistoryRunDetail
            v-if="detailCache[row.id]"
            :parameters="detailCache[row.id].parameters"
          />
          <div v-else class="run-detail-loading">加载中…</div>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{
          formatDateTime(row.finished_at)
        }}</template>
      </el-table-column>
      <el-table-column label="文件名" min-width="220">
        <template #default="{ row }">
          <span
            class="run-filename"
            :title="row.report_filename || row.log_filename || '-'"
          >
            {{
              row.report_filename || row.log_filename || "无报告（失败/停止）"
            }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ STATUS_LABEL[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center">
        <template #default="{ row }">
          <el-tooltip content="下载报告" placement="top">
            <el-button
              size="small"
              type="success"
              plain
              :icon="Download"
              :disabled="!row.report_available"
              aria-label="下载报告"
              @click="downloadReport(row)"
            />
          </el-tooltip>
          <el-tooltip content="下载日志" placement="top">
            <el-button
              size="small"
              plain
              :icon="Document"
              :disabled="!row.log_available"
              aria-label="下载日志"
              @click="downloadLog(row)"
            />
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!runs.length && !loading" :image-size="52">
      <template #image>
        <el-icon aria-hidden="true"><Clock /></el-icon>
      </template>
      <template #description>
        <p>{{ configName ? '暂无该项目的比对记录' : '请先选择项目' }}</p>
      </template>
    </el-empty>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.dialog-subtitle {
  color: var(--color-text-secondary);
  font-size: var(--font-sm);
}

.run-filename {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.run-detail-loading {
  color: var(--color-text-muted);
  padding: 8px;
  font-size: var(--font-sm);
}
</style>
