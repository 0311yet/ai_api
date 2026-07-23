<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { NCard, NSpin, NTag, NEmpty, NProgress, NButton, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import { healthAPI } from '../api'

const loading = ref(false)
const message = useMessage()
const pools = ref<any[]>([])
const stickyActive = ref(0)

interface KeyHealth {
  platform_key_id: number
  key_label: string
  is_active: boolean
  rate_window: { rpm: number; rpd: number; tpm: number; tpd: number }
  cooldown_until: string | null
  strike_count: number
  penalty_score: number
  effective_priority: number
}

// interfaces inlined via :any in template

function getStatus(k: KeyHealth) {
  if (!k.is_active) return { type: 'warning', label: 'Disabled' } as const
  if (k.cooldown_until) return { type: 'error', label: 'Cooldown' } as const
  if (k.penalty_score >= 5) return { type: 'warning', label: 'High Penalty' } as const
  if (k.rate_window.rpm > 50 || k.rate_window.tpm > 5000) return { type: 'warning', label: 'High Load' } as const
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
            <h1 class="text-[20px] font-semibold text-text-primary">Platform Health</h1>
            <p class="text-sm text-text-secondary mt-0.5">
              Monitor platforms, rate limits, cooldowns, and penalties.
              Each model shows all available keys — backend auto-selects on each request.
            </p>
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
          <span class="text-text-secondary">{{ stickyActive }} conversation(s) locked to specific keys</span>
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
              <NTag size="tiny" :type="(pool.items?.length || 0) > 0 ? 'success' : 'warning'">
                {{ pool.items?.length || 0 }} model(s)
              </NTag>
            </div>
          </template>

          <!-- Empty state -->
          <NEmpty
            v-if="!pool.items?.length"
            size="small"
            description="No models in this pool. Add models in Pools management."
            class="py-8"
          />

          <!-- Pool item grid -->
          <div
            v-else
            class="grid gap-3 p-4"
            :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }"
          >
            <!-- Each PoolItem = Platform + Model combination -->
            <div
              v-for="item in pool.items"
              :key="item.pool_item_id"
              class="bg-surface-container-lowest border border-border rounded-xl overflow-hidden"
            >
              <!-- PoolItem header -->
              <div class="px-4 pt-4 pb-3 border-b border-border">
                <div class="flex items-center gap-1.5 mb-1.5">
                  <NTag size="small" type="info">Platform #{{ item.platform_id }}</NTag>
                  <NTag size="small" :type="item.is_active ? 'success' : 'warning'" round>
                    {{ item.is_active ? 'Active' : 'Disabled' }}
                  </NTag>
                  <span class="ml-auto text-[11px] text-text-secondary font-mono">
                    prio {{ item.priority }}
                  </span>
                </div>
                <div class="font-semibold text-sm text-text-primary truncate">{{ item.platform_name }}</div>
                <div class="font-mono text-[13px] text-primary font-semibold mt-1">{{ item.model }}</div>
                <div class="font-mono text-[11px] text-text-secondary truncate mt-0.5" :title="item.base_url">
                  {{ item.base_url }}
                </div>
              </div>

              <!-- Keys list -->
              <div class="px-4 py-3 space-y-2">
                <div
                  v-for="k in item.available_keys"
                  :key="k.platform_key_id"
                  class="bg-surface-container-low rounded-lg p-3"
                >
                  <!-- Key header -->
                  <div class="flex items-center gap-1.5 mb-2">
                    <span class="font-mono text-[11px] text-text-secondary">#{{ k.platform_key_id }}</span>
                    <NTag size="tiny" type="info" round>key-{{ k.key_label }}</NTag>
                    <NTag size="tiny" :type="getStatus(k).type" round>{{ getStatus(k).label }}</NTag>
                  </div>

                  <!-- Rate window -->
                  <div class="grid grid-cols-4 gap-1 text-[11px] mb-2">
                    <div class="text-center">
                      <div class="font-mono font-bold text-text-primary">{{ k.rate_window.rpm }}</div>
                      <div class="text-text-secondary">RPM</div>
                    </div>
                    <div class="text-center">
                      <div class="font-mono font-bold text-text-primary">{{ k.rate_window.rpd }}</div>
                      <div class="text-text-secondary">RPD</div>
                    </div>
                    <div class="text-center">
                      <div class="font-mono font-bold text-text-primary">{{ k.rate_window.tpm }}</div>
                      <div class="text-text-secondary">TPM</div>
                    </div>
                    <div class="text-center">
                      <div class="font-mono font-bold text-text-primary">{{ k.rate_window.tpd }}</div>
                      <div class="text-text-secondary">TPD</div>
                    </div>
                  </div>

                  <!-- Penalty & priority -->
                  <div class="grid grid-cols-2 gap-2 mb-2">
                    <div class="bg-surface-container-lowest p-1.5 rounded text-center">
                      <div class="text-[10px] text-text-secondary">Effective Prio</div>
                      <div class="font-mono text-[13px] font-bold text-text-primary">{{ k.effective_priority }}</div>
                    </div>
                    <div class="bg-surface-container-lowest p-1.5 rounded text-center">
                      <div class="text-[10px] text-text-secondary">Penalty</div>
                      <div class="font-mono text-[13px] font-bold"
                        :class="k.penalty_score === 0 ? 'text-success' : k.penalty_score <= 2 ? 'text-warning' : 'text-error'">
                        {{ k.penalty_score }}
                      </div>
                    </div>
                  </div>

                  <!-- Cooldown -->
                  <div v-if="k.cooldown_until" class="mt-1">
                    <div class="flex items-center justify-between text-[10px] mb-0.5">
                      <span class="text-error font-semibold">Cooldown</span>
                      <span class="text-error font-mono font-bold">{{ cooldownRemaining(k.cooldown_until) }}</span>
                    </div>
                    <NProgress
                      type="line"
                      :percentage="cooldownProgress(k.cooldown_until)"
                      :height="4"
                      :border-radius="2"
                      :fill-border-radius="2"
                      :show-indicator="false"
                      :processing="true"
                      :rail-color="'#2e2e42'"
                    />
                    <div v-if="k.strike_count > 0" class="text-[10px] text-warning mt-0.5">
                      ⚠ {{ k.strike_count }} strike(s)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </NCard>

        <!-- Global empty state -->
        <NEmpty v-if="!pools.length" description="No pools configured." />
      </template>
    </div>
  </div>
</template>