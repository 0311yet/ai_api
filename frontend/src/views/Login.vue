<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!password.value) {
    message.warning('请输入 Admin Key')
    return
  }
  loading.value = true
  try {
    const ok = await auth.login(password.value)
    if (ok) {
      router.push('/dashboard')
    } else {
      message.error('Admin Key 错误')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-background flex items-center justify-center">
    <div class="w-full max-w-sm px-6">
      <!-- Logo -->
      <div class="flex flex-col items-center mb-10">
        <div class="w-14 h-14 rounded-2xl bg-primary-container flex items-center justify-center mb-4 shadow-[0_0_30px_rgba(64,158,255,0.3)]">
          <span class="material-symbols-outlined text-white text-[28px]">widgets</span>
        </div>
        <h1 class="text-xl font-semibold text-text-primary">AI Gateway</h1>
        <p class="text-sm text-text-secondary mt-1">Infrastructure Admin</p>
      </div>

      <!-- Card -->
      <div class="bg-surface-container border border-border rounded-xl p-6">
        <h2 class="text-base font-semibold text-text-primary mb-1">登录管理后台</h2>
        <p class="text-sm text-text-secondary mb-5">输入 Admin Key 以访问控制台</p>

        <div class="mb-5">
          <NInput
            v-model:value="password"
            type="password"
            placeholder="请输入 Admin Key"
            size="large"
            :disabled="loading"
            show-password-on="mousedown"
            @keyup.enter="handleLogin"
          />
        </div>

        <NButton
          type="primary"
          size="large"
          block
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </NButton>
      </div>
    </div>
  </div>
</template>