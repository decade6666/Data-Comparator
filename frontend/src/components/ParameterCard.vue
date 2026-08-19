<script setup>
import { computed } from 'vue'
import { Edit } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, required: true },
  type: { type: String, required: true },
  value: { type: [Array, Object], default: () => [] },
})

defineEmits(['edit'])

function entryLabel(entry) {
  if (Array.isArray(entry)) return entry.join(', ')
  if (entry && typeof entry === 'object') return Object.entries(entry).map(([k, v]) => `${k}: ${v.join(', ')}`)
  return String(entry)
}

const tags = computed(() => {
  if (Array.isArray(props.value)) return props.value.map(entryLabel)
  if (props.value && typeof props.value === 'object') {
    return Object.entries(props.value).map(([k, v]) => `${k}: ${v.join(', ')}`)
  }
  return []
})
</script>

<template>
  <div class="parameter-card">
    <span class="parameter-card-title">{{ title }}</span>
    <div class="parameter-card-tags">
      <div v-if="tags.length" class="tag-cloud">
        <el-tag v-for="(tag, index) in tags" :key="index" size="small" type="info">
          {{ tag }}
        </el-tag>
      </div>
    </div>
    <el-button
      :icon="Edit"
      size="small"
      title="修改"
      aria-label="修改"
      @click="$emit('edit')"
    />
  </div>
</template>
