<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { NCard, NSpin, NTag, NEmpty, NProgress, NButton, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import { healthAPI } from '../api'

const loading = ref(false)
const message = useMessage()
const pools = ref<any[]>([])
const stickyActive = ref(0)

interface ProviderHealth {
  provider_id: number
  provider_name: string
  base_url: string
  is_active: boolean
  rate_window: { rpm: number; rpd: number; tpm: number; tpd: number }
  cooldown_until: string | null
  strike_count: number
  penalty_score: number
  effective_priority: number
}

function getStatus(p: ProviderHealth) {
  if (!p.is_active) return { type: 'warning', label: 'Disabled' } as const
  if (p.cooldown_until) return { type: 'error', label: 'Cooldown' } as const
  if (p.penalty_score >= 5) return { type: 'warning', label: 'High Penalty' } as const
  if (p.rate_window.rpm > 50 || p.rate_window.tpm > 5000) return { type: 'warning', label: 'High Load' } as const
  return { type: 'success', label: 'Healthy' } as const
}

function cooldownRemaining(until: string | null): string {
  if (!until) return ''
  const now = Date.now() / 1000
  const t = new Date(until).getTime() / 1000
  const s = Math.max(0, Math.round(t - now))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  if (s < 86400) return `${Math.round(s / 3600)}h`
  return `${Math.round(s / 86400)}d`
}

function cooldownProgress(until: string | null): number {
  if (!until) return 0
  const now = Date.now() / 1000
  const t = new Date(until).getTime() / 1000
  const elapsed = Math.max(0, Math.min(1, (now - (t - 1800)) / 1800))
  return Math.round(elapsed * 100)
}

const REFRESH_INTERVAL_MS = 3000
let refreshTimer: ReturnType<typeof setInterval> | null = null
const lastUpdated = ref<string>('')

async function load(manual: boolean = false) {
  if (manual) loading.value = true
  try {
    const { data } = await healthAPI.overview()
    pools.value = data.pools || []
    stickyActive.value = data.sticky_sessions_active || 0
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    message.error('加载失败: ' + (e?.message || '未知错误'))
    console.error(e)
  } finally {
    if (manual) loading.value = false
  }
}

function manualRefresh() {
  load(true)
  // 手动刷新后重置 3s 倍表，避免点完快临近下一轮
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = setInterval(load, REFRESH_INTERVAL_MS)
  }
}

onMounted(() => {
  load(true)
  refreshTimer = setInterval(load, REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Routing' }, { label: 'Health', active: true }]">
      <template #actions>
        <NButton type="primary" size="small" @click="manualRefresh" :loading="loading">
          <template #icon>
            <span class="material-symbols-outlined text-base">refresh</span>
          </template>
          Refresh
        </NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <!-- Header -->
      <div>
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h1 class="text-[20px] font-semibold text-text-primary">Provider Health</h1>
            <p class="text-sm text-text-secondary mt-0.5">Monitor upstream providers, rate limits, cooldowns, and penalties</p>
          </div>
          <div class="flex items-center gap-1.5 text-xs text-text-secondary font-mono">
            <span class="w-1.5 h-1.5 rounded-full bg-success inline-block animate-pulse"></span>
            <span class="text-success font-semibold">LIVE</span>
            <span class="opacity-60">· auto-refresh 3s · updated {{ lastUpdated || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- Sticky Sessions Banner -->
      <NCard v-if="stickyActive > 0" size="small"
        class="!border-primary/40 !bg-primary/5">
        <div class="flex items-center gap-2 text-sm">
          <span class="material-symbols-outlined text-primary text-base">auto_awesome</span>
          <span class="text-primary font-semibold">Sticky Sessions Active:</span>
          <span class="text-text-secondary">{{ stickyActive }} conversation(s) locked to specific providers</span>
        </div>
      </NCard>

      <NSpin v-if="loading" class="self-center py-16" size="large" />

      <template v-else>
        <!-- Pools -->
        <NCard
          v-for="pool in pools"
          :key="pool.pool_id"
          size="small"
          :bordered="true"
          :content-style="{ padding: '0' }"
          class="!border-border"
        >
          <template #header>
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-semibold text-sm text-text-primary">{{ pool.pool_name }}</span>
              <NTag size="tiny" type="info">{{ pool.strategy }}</NTag>
              <NTag
                size="tiny"
                :type="pool.providers?.length > 0 ? 'success' : 'warning'"
              >
                {{ pool.providers?.length || 0 }} provider(s)
              </NTag>
            </div>
          </template>

          <!-- No providers -->
          <NEmpty
            v-if="!pool.providers?.length"
            size="small"
            description="No providers in this pool. Add providers in Pools management."
            class="py-8"
          />

          <!-- Provider grid -->
          <div
            v-else
            class="grid gap-3 p-4"
            :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }"
          >
            <div
              v-for="p in pool.providers"
              :key="p.provider_id"
              class="bg-surface-container-lowest border border-border rounded-xl p-4 hover:border-primary/50 transition-colors"
            >
              <!-- Provider header -->
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5">
                    <span class="font-mono text-[11px] text-text-secondary">#{{ p.provider_id }}</span>
                    <NTag size="tiny" :type="getStatus(p).type" round>{{ getStatus(p).label }}</NTag>
                  </div>
                  <div class="font-semibold text-sm text-text-primary mt-1 truncate" :title="p.provider_name">
                    {{ p.provider_name }}
                  </div>
                  <div class="mt-1 flex items-center gap-1 flex-wrap"
                    v-if="p.model"
                  >
                    <span class="font-mono text-[11px] font-semibold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                      {{ p.model }}
                    </span>
                  </div>
                  <div class="font-mono text-[11px] text-text-secondary mt-0.5 truncate" :title="p.base_url">
                    {{ p.base_url }}
                  </div>
                </div>
              </div>

              <!-- Priority / Penalty row -->
              <div class="mt-3 grid grid-cols-2 gap-2">
                <div class="bg-surface-container-low p-2 rounded-lg">
                  <div class="text-[11px] text-text-secondary">Effective Priority</div>
                  <div class="font-mono text-sm font-bold text-text-primary mt-0.5">
                    {{ p.effective_priority }}
                  </div>
                  <div class="text-[10px] text-text-secondary font-mono">base − {{ p.penalty_score }}</div>
                </div>
                <div class="bg-surface-container-low p-2 rounded-lg">
                  <div class="text-[11px] text-text-secondary">Penalty Score</div>
                  <div
                    class="font-mono text-sm font-bold mt-0.5"
                    :class="p.penalty_score === 0 ? 'text-success' : p.penalty_score <= 2 ? 'text-warning' : 'text-error'"
                  >
                    {{ p.penalty_score }}
                  </div>
                  <div v-if="p.strike_count > 0" class="text-[10px] text-warning font-mono">
                    ⚠ {{ p.strike_count }} strike(s)
                  </div>
                </div>
              </div>

              <!-- Cooldown -->
              <div v-if="p.cooldown_until" class="mt-3">
                <div class="flex items-center justify-between text-[11px] mb-1">
                  <span class="text-error font-semibold">Cooldown</span>
                  <span class="text-error font-mono font-bold">{{ cooldownRemaining(p.cooldown_until) }}</span>
                </div>
                <NProgress
                  type="line"
                  :percentage="cooldownProgress(p.cooldown_until)"
                  :height="6"
                  :border-radius="3"
                  :fill-border-radius="3"
                  :show-indicator="false"
                  :processing="true"
                  :rail-color="'#2e2e42'"
                />
                <div class="text-[10px] text-text-secondary mt-1">
                  {{ p.strike_count }} strike(s) → cooldown escalation active
                </div>
              </div>

              <!-- Rate Window -->
              <div class="mt-3">
                <div class="text-[11px] text-text-secondary mb-1">Rate Window (1h / 24h)</div>
                <div class="grid grid-cols-2 gap-1">
                  <div class="flex justify-between text-[12px]">
                    <span class="text-text-secondary">RPM</span>
                    <span class="font-mono font-bold text-text-primary">{{ p.rate_window.rpm }}</span>
                  </div>
                  <div class="flex justify-between text-[12px]">
                    <span class="text-text-secondary">RPD</span>
                    <span class="font-mono font-bold text-text-primary">{{ p.rate_window.rpd }}</span>
                  </div>
                  <div class="flex justify-between text-[12px]">
                    <span class="text-text-secondary">TPM</span>
                    <span class="font-mono font-bold text-text-primary">{{ p.rate_window.tpm }}</span>
                  </div>
                  <div class="flex justify-between text-[12px]">
                    <span class="text-text-secondary">TPD</span>
                    <span class="font-mono font-bold text-text-primary">{{ p.rate_window.tpd }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </NCard>

        <!-- Empty state -->
        <NEmpty v-if="!pools.length" description="No pools configured." />
      </template>
    </div>
  </div>
</template>