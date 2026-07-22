<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: 'dashboard' },
  { name: 'Providers', path: '/providers', icon: 'hub' },
  { name: 'Pools', path: '/pools', icon: 'database' },
  { name: 'Keys', path: '/keys', icon: 'key' },
  { name: 'Logs', path: '/logs', icon: 'receipt_long' },
  { name: 'Stats', path: '/stats', icon: 'query_stats' },
]

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-screen bg-background overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-[220px] shrink-0 bg-surface-container-low border-r border-border flex flex-col py-6 px-4 z-50">
      <!-- Logo -->
      <div class="flex items-center gap-3 mb-8 px-2">
        <div class="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(64,158,255,0.2)]">
          <span class="material-symbols-outlined text-white text-[18px]">widgets</span>
        </div>
        <div>
          <div class="font-semibold text-sm leading-tight">AI Gateway</div>
          <div class="text-[12px] text-text-secondary leading-tight">Infrastructure Admin</div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 flex flex-col gap-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-sm"
          :class="route.path === item.path
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-on-surface-variant hover:text-text-primary hover:bg-surface-container-high'"
        >
          <span class="material-symbols-outlined text-[20px]"
            :class="route.path === item.path ? 'font-fill' : ''">
            {{ item.icon }}
          </span>
          {{ item.name }}
        </router-link>
      </nav>

      <!-- Bottom -->
      <div class="mt-auto flex flex-col gap-3">
        <button
          class="w-full text-left px-3 py-2 rounded-lg text-on-surface-variant hover:text-text-primary hover:bg-surface-container-high transition-colors text-sm flex items-center gap-3"
          @click="logout"
        >
          <span class="material-symbols-outlined text-[20px]">logout</span>
          退出登录
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-auto">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.font-fill {
  font-variation-settings: 'FILL' 1;
}
</style>