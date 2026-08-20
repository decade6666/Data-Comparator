<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  maxWorkers: { type: Number, default: 4 },
  isDark: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
})

defineEmits(['update:modelValue', 'update:maxWorkers', 'update:isDark', 'change-password', 'logout'])
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
      <el-form-item v-if="!isAdmin" label="最大线程数">
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
    <div class="settings-actions">
      <el-button @click="$emit('change-password')">修改密码</el-button>
      <el-button type="danger" @click="$emit('logout')">退出登录</el-button>
    </div>
  </el-dialog>
</template>

<style scoped>
.settings-actions {
  display: flex;
  gap: var(--space-md);
  margin-top: var(--space-lg);
}
</style>
