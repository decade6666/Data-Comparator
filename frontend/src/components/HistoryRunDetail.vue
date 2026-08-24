<script setup>
import { computed } from "vue";
import ParameterCard from "./ParameterCard.vue";

const props = defineProps({
  parameters: { type: Object, default: () => ({}) },
});

function colorLabel(key) {
  const map = {
    highlight_fill: "更新颜色",
    missing_sheet_tab: "删除颜色",
    new_sheet_tab: "新增颜色",
  };
  return map[key] || key;
}

const structureRows = computed(() => {
  const p = props.parameters || {};
  return [
    { label: "锚点行号", value: p.anchor_row_num ?? "-" },
    { label: "表头行号", value: p.header_row_num ?? "-" },
    {
      label: "删除数据",
      value: p.merge_deleted_data === false ? "舍弃" : "保留",
    },
    { label: "锚点标识列", value: p.anchor_row_content || "-" },
    { label: "表头标识列", value: p.header_row_content || "-" },
    { label: "最大线程数", value: p.max_workers ?? "-" },
  ];
});

const cards = computed(() => {
  const p = props.parameters || {};
  const include = p.include_sheets || [];
  const exclude = p.exclude_sheets || [];
  return [
    {
      key: "common_cols",
      title: "排除字段",
      type: "list",
      value: p.common_cols || [],
    },
    {
      key: "sheet_scope",
      title: "比对表单",
      type: "list",
      value: [
        ...(include.length ? [`包含：${include.join(", ")}`] : []),
        ...(exclude.length ? [`排除：${exclude.join(", ")}`] : []),
      ],
    },
    {
      key: "ignore_settings",
      title: "忽略字段",
      type: "fields",
      value: {
        global: p.ignore_cols || [],
        perSheet: p.sheet_ignore_cols || {},
      },
    },
    {
      key: "anchor_settings",
      title: "锚点",
      type: "anchors",
      value: {
        global: p.default_keys || [],
        perSheet: p.sheet_key_map || {},
      },
    },
    {
      key: "sheet_order",
      title: "表单顺序",
      type: "order",
      value: p.sheet_order || [],
    },
  ];
});

const colors = computed(() => props.parameters?.colors || {});
</script>

<template>
  <div class="run-detail">
    <div class="run-detail-section">
      <h5>结构设置</h5>
      <dl class="run-detail-dl">
        <template v-for="row in structureRows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </template>
      </dl>
    </div>

    <div class="run-detail-section">
      <h5>比对参数</h5>
      <ParameterCard
        v-for="card in cards"
        :key="card.key"
        :title="card.title"
        :type="card.type"
        :value="card.value"
        :readonly="true"
      />
    </div>

    <div class="run-detail-section" v-if="Object.keys(colors).length">
      <h5>颜色设置</h5>
      <div class="run-detail-colors">
        <span v-for="(val, key) in colors" :key="key" class="color-chip">
          <span class="color-swatch" :style="{ background: val }" />
          {{ colorLabel(key) }}：{{ val }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.run-detail {
  padding: 4px 8px 8px;
}

.run-detail-section {
  margin-bottom: var(--space-md);
}

.run-detail-section h5 {
  color: var(--color-primary-dark);
  font-size: var(--font-sm);
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.run-detail-dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  font-size: var(--font-sm);
}

.run-detail-dl dt {
  color: var(--color-text-secondary);
}

.run-detail-dl dd {
  color: var(--color-text-primary);
}

.run-detail-colors {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  font-size: var(--font-sm);
}

.color-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
}

.color-swatch {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  display: inline-block;
}
</style>
