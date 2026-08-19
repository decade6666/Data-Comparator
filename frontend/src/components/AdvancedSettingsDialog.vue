<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  maxWorkers: { type: Number, default: 4 },
  isDark: { type: Boolean, default: false },
})

defineEmits(['update:modelValue', 'update:maxWorkers', 'update:isDark'])
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="高级设置"
    width="420px"
    append-to-body
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form label-width="110px" label-position="left">
      <el-form-item label="最大线程数">
        <el-input-number
          :model-value="maxWorkers"
          :min="1"
          :max="64"
          @update:model-value="$emit('update:maxWorkers', $event)"
        />
      </el-form-item>
      <el-form-item label="深色模式">
        <el-switch
          :model-value="isDark"
          @update:model-value="$emit('update:isDark', $event)"
        />
      </el-form-item>
    </el-form>
  </el-dialog>
</template>
