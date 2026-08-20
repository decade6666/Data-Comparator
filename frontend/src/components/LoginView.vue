<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useAuth } from '../composables/useAuth'

const emit = defineEmits(['logged-in'])
const { login } = useAuth()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await login(username.value.trim(), password.value)
    emit('logged-in')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <el-card class="login-card">
      <template #header><h1>数据集比对工具</h1></template>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input
            v-model="username"
            :prefix-icon="User"
            autocomplete="username"
            autofocus
            placeholder="请输入用户名"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            :prefix-icon="Lock"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="请输入密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" native-type="submit" class="login-submit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--color-bg, #f5f7fa);
}

.login-card {
  width: min(92vw, 380px);
}

.login-card h1 {
  margin: 0;
  font-size: 20px;
  text-align: center;
}

.login-submit {
  width: 100%;
}
</style>
