<script setup>
import { computed } from "vue";

const props = defineProps({
  progress: { type: Number, default: 0 },
  message: { type: String, default: "准备就绪" },
  status: { type: String, default: "idle" },
  scanning: { type: Boolean, default: false },
});

const displayProgress = computed(() =>
  props.status === "idle" ? 0 : props.progress,
);

const barColor = computed(() => {
  if (props.status === "failed") return "#ef4444";
  if (props.status === "cancelled") return "#f59e0b";
  if (props.status === "completed") return "#22c55e";
  return undefined;
});
</script>

<template>
  <div class="panel">
    <div class="panel-header">进度</div>
    <div class="panel-body">
      <div class="progress-label">
        <span>{{ props.scanning ? `扫描文件中…` : message }}</span>
      </div>
      <el-progress
        :percentage="Math.round(displayProgress)"
        :stroke-width="14"
        striped
        :color="barColor"
      />
    </div>
  </div>
</template>
