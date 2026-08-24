<script setup>
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  CircleClose,
  Clock,
  Document,
  Download,
  FolderChecked,
  RefreshLeft,
  VideoPlay,
} from "@element-plus/icons-vue";
import {
  saveConfigWithPrompt,
  revertConfig,
  currentName,
} from "../composables/useConfigState";
import HistoryDialog from "./HistoryDialog.vue";

const props = defineProps({
  status: { type: String, default: "idle" },
  hasLogs: { type: Boolean, default: false },
  scanning: { type: Boolean, default: false },
});

defineEmits(["start", "stop", "download-report", "download-logs"]);

const historyVisible = ref(false);

const running = computed(
  () =>
    props.scanning ||
    ["pending", "running", "cancelling"].includes(props.status),
);
const finished = computed(() => props.status === "completed");

async function saveParameters() {
  try {
    const name = await saveConfigWithPrompt();
    if (name) ElMessage.success(`已保存：${name}`);
  } catch (err) {
    ElMessage.error(err.message);
  }
}

function cancelSave() {
  revertConfig();
  ElMessage.success("已撤销未保存的修改");
}
</script>

<template>
  <div class="panel action-panel">
    <div class="panel-header">操作</div>
    <div class="panel-body action-bar">
      <div class="action-bar-primary">
        <el-button
          v-if="!running"
          type="primary"
          size="large"
          :icon="VideoPlay"
          class="action-start-btn"
          aria-label="开始比对"
          @click="$emit('start')"
        >
          开始比对
        </el-button>
        <el-button
          v-else
          type="danger"
          size="large"
          :icon="CircleClose"
          class="action-start-btn"
          :disabled="props.status === 'cancelling'"
          aria-label="停止比对"
          @click="$emit('stop')"
        >
          停止比对
        </el-button>
      </div>
      <div class="action-bar-secondary">
        <el-tooltip content="下载报告" placement="top">
          <el-button
            v-if="finished"
            size="small"
            type="success"
            plain
            :icon="Download"
            aria-label="下载报告"
            @click="$emit('download-report')"
          />
        </el-tooltip>
        <el-tooltip content="下载日志" placement="top">
          <el-button
            v-if="hasLogs"
            size="small"
            plain
            :icon="Document"
            aria-label="下载日志"
            @click="$emit('download-logs')"
          />
        </el-tooltip>
        <el-tooltip content="历史记录" placement="top">
          <el-button
            size="small"
            plain
            :icon="Clock"
            aria-label="历史记录"
            @click="historyVisible = true"
          />
        </el-tooltip>
        <span class="action-bar-divider" />
        <el-tooltip content="保存项目" placement="top">
          <el-button
            size="small"
            type="primary"
            plain
            :icon="FolderChecked"
            aria-label="保存项目"
            @click="saveParameters"
          />
        </el-tooltip>
        <el-tooltip content="取消保存" placement="top">
          <el-button
            size="small"
            plain
            :icon="RefreshLeft"
            aria-label="取消保存"
            @click="cancelSave"
          />
        </el-tooltip>
      </div>
    </div>
    <HistoryDialog v-model="historyVisible" :config-name="currentName" />
  </div>
</template>

<style scoped>
.action-panel {
  position: sticky;
  bottom: 0;
  z-index: 1;
  margin-bottom: 0;
  background: var(--color-bg-card);
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  flex-wrap: wrap;
}

.action-bar-primary {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-shrink: 0;
}

.action-start-btn {
  min-width: 180px;
  height: 44px;
  font-size: var(--font-md);
  font-weight: 600;
  letter-spacing: 2px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-primary);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.action-start-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-raised);
}

.action-start-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

.action-bar-secondary {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.action-bar-secondary .el-button + .el-button {
  margin-left: 0;
}

.action-bar-divider {
  width: 1px;
  height: 20px;
  background: var(--color-border);
  margin: 0 4px;
}
</style>
