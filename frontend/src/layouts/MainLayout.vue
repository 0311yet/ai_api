<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const navGroups = [
  { label: 'Workspace', items: [
    { name: 'Overview', path: '/dashboard', icon: 'dashboard' },
    { name: 'Providers', path: '/platforms', icon: 'hub' },
    { name: 'Model pools', path: '/pools', icon: 'database' },
    { name: 'API keys', path: '/keys', icon: 'key' },
  ] },
  { label: 'Operations', items: [
    { name: 'Request logs', path: '/logs', icon: 'receipt_long' },
    { name: 'Analytics', path: '/stats', icon: 'query_stats' },
    { name: 'Health', path: '/health', icon: 'sensors' },
    { name: 'Rates', path: '/rates', icon: 'paid' },
  ] },
]

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell flex h-screen bg-background overflow-hidden">
    <aside class="app-sidebar w-[244px] shrink-0 bg-surface-container-low border-r border-border flex flex-col py-5 px-3 z-50">
      <div class="flex items-center gap-3 mb-8 px-3">
        <div class="brand-mark w-9 h-9 rounded-xl flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-white text-[19px]">bolt</span></div>
        <div><div class="font-semibold text-[14px] leading-tight tracking-tight">Relay Console</div><div class="text-[11px] text-text-secondary leading-tight mt-0.5">AI infrastructure</div></div>
      </div>
      <nav class="flex-1 flex flex-col gap-6">
        <div v-for="group in navGroups" :key="group.label">
          <div class="px-3 mb-2 text-[10px] uppercase tracking-[0.16em] text-text-secondary font-semibold">{{ group.label }}</div>
          <div class="flex flex-col gap-0.5">
            <router-link v-for="item in group.items" :key="item.path" :to="item.path" class="nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-[13px]" :class="route.path === item.path ? 'nav-item-active text-primary font-medium' : 'text-on-surface-variant hover:text-text-primary hover:bg-surface-container-high'">
              <span class="material-symbols-outlined text-[19px]" :class="route.path === item.path ? 'font-fill' : ''">{{ item.icon }}</span>{{ item.name }}
            </router-link>
          </div>
        </div>
      </nav>
      <div class="mt-auto pt-4 border-t border-border flex flex-col gap-3">
        <div class="px-3 py-2 text-[11px] text-text-secondary flex items-center gap-2"><span class="status-dot"></span>Gateway operational</div>
        <button class="w-full text-left px-3 py-2 rounded-lg text-on-surface-variant hover:text-text-primary hover:bg-surface-container-high transition-colors text-[13px] flex items-center gap-3" @click="logout"><span class="material-symbols-outlined text-[20px]">logout</span>Sign out</button>
      </div>
    </aside>
    <main class="flex-1 overflow-auto"><router-view /></main>
  </div>
</template>

<style scoped>.font-fill { font-variation-settings: 'FILL' 1; }</style>
