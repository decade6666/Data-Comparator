<script setup>
import { computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import { parameterDescription } from '../constants/parameterDescriptions'

const props = defineProps({
  title: { type: String, required: true },
  type: { type: String, required: true },
  value: { type: [Array, Object], default: () => [] },
  description: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
})

defineEmits(['edit'])

function entryLabel(entry) {
  if (Array.isArray(entry)) return entry.join(', ')
  if (entry && typeof entry === 'object') {
    return Object.entries(entry)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
      .join('；')
  }
  return String(entry)
}

const tags = computed(() => {
  if (Array.isArray(props.value)) return props.value.map(entryLabel)
  if (props.value && typeof props.value === 'object') {
    if ('global' in props.value || 'perSheet' in props.value) {
      const global = Array.isArray(props.value.global) ? props.value.global : []
      const perSheet = props.value.perSheet || {}
      return [
        ...(global.length ? [`全局：${global.join(', ')}`] : []),
        ...Object.entries(perSheet).map(([key, value]) => `${key}：${value.join(', ')}`),
      ]
    }
    return Object.entries(props.value).map(([key, value]) => `${key}：${entryLabel(value)}`)
  }
  return []
})

const tooltip = computed(() => props.description || parameterDescription(props.title))
</script>

<template>
  <div class="parameter-card">
    <el-tooltip :content="tooltip" placement="top-start">
      <span class="parameter-card-title parameter-card-title-help">{{ title }}</span>
    </el-tooltip>
    <div class="parameter-card-tags">
      <div v-if="tags.length" class="tag-cloud">
        <el-tag v-for="(tag, index) in tags" :key="index" size="small" type="info">
          {{ tag }}
        </el-tag>
      </div>
    </div>
    <el-button
      v-if="!readonly"
      :icon="Edit"
      size="small"
      title="修改"
      aria-label="修改"
      @click="$emit('edit')"
    />
  </div>
</template>
