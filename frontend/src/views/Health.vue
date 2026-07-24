<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { NCard, NSpin, NTag, NEmpty, NProgress, NButton, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import { healthAPI } from '../api'

const loading = ref(false)
const message = useMessage()
const platforms = ref<any[]>([])
const stickyActive = ref(0)

interface KeyHealth {
  platform_key_id: number
  key_label: string
  is_active: boolean
  rate_window: { rpm: number; rpd: number; tpm: number; tpd: number }
  cooldown_until: string | null
  strike_count: number
  penalty_score: number
}

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
    const { data } = await healthAPI.platforms()
    platforms.value = data.platforms || []
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
              监控所有平台 API Keys 的用量、限速与健康状态。
              无模型分层，每个 Key 显示其所有模型的聚合数据。
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
        <!-- Platforms grid: 2 columns, side by side -->
        <div
          class="grid gap-4"
          :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(560px, 1fr))' }"
        >
          <NCard
            v-for="platform in platforms"
            :key="platform.platform_id"
            size="small"
            :bordered="true"
            :content-style="{ padding: '0' }"
            class="!border-border"
          >
            <template #header>
              <div class="flex items-center gap-3 flex-wrap">
                <span class="font-semibold text-sm text-text-primary">{{ platform.platform_name }}</span>
                <span class="font-mono text-[12px] text-text-secondary truncate max-w-xs" :title="platform.base_url">
                  {{ platform.base_url }}
                </span>
                <NTag size="tiny" :type="(platform.keys?.length || 0) > 0 ? 'success' : 'warning'">
                  {{ platform.keys?.length || 0 }} key(s)
                </NTag>
              </div>
            </template>

            <!-- Empty state -->
            <NEmpty
              v-if="!platform.keys?.length"
              size="small"
              description="No active keys in this platform."
              class="py-8"
            />

            <!-- Keys: vertical list -->
            <div
              v-else
              class="flex flex-col gap-2 p-4"
            >
            <div
              v-for="k in platform.keys"
              :key="k.platform_key_id"
              class="bg-surface-container-lowest border border-border rounded-xl overflow-hidden"
            >
              <!-- Key header -->
              <div class="flex items-center gap-2 px-4 pt-3 pb-2 border-b border-border">
                <span class="font-mono text-[12px] text-text-secondary">#{{ k.platform_key_id }}</span>
                <NTag size="small" type="info" round>key-{{ k.key_label }}</NTag>
                <NTag size="small" :type="getStatus(k).type" round>{{ getStatus(k).label }}</NTag>
                <span v-if="!k.is_active" class="ml-auto">
                  <NTag size="tiny" type="warning">Disabled</NTag>
                </span>
              </div>

              <!-- Rate window + details -->
              <div class="flex items-center gap-3 px-4 py-3 flex-wrap">
                <div class="grid grid-cols-4 gap-6 text-[11px]">
                  <div class="text-center">
                    <div class="font-mono font-bold text-[15px] text-text-primary">{{ k.rate_window.rpm }}</div>
                    <div class="text-text-secondary">RPM</div>
                  </div>
                  <div class="text-center">
                    <div class="font-mono font-bold text-[15px] text-text-primary">{{ k.rate_window.rpd }}</div>
                    <div class="text-text-secondary">RPD</div>
                  </div>
                  <div class="text-center">
                    <div class="font-mono font-bold text-[15px] text-text-primary">{{ k.rate_window.tpm }}</div>
                    <div class="text-text-secondary">TPM</div>
                  </div>
                  <div class="text-center">
                    <div class="font-mono font-bold text-[15px] text-text-primary">{{ k.rate_window.tpd }}</div>
                    <div class="text-text-secondary">TPD</div>
                  </div>
                </div>

                <!-- Penalty -->
                <div class="flex items-center gap-1 text-[11px]">
                  <span class="text-text-secondary">Penalty</span>
                  <span
                    class="font-mono font-bold"
                    :class="k.penalty_score === 0 ? 'text-success' : k.penalty_score <= 2 ? 'text-warning' : 'text-error'"
                  >{{ k.penalty_score }}</span>
                </div>
                <div v-if="k.strike_count > 0" class="flex items-center gap-1 text-[11px]">
                  <span class="text-text-secondary">Strikes</span>
                  <span class="font-mono font-bold text-warning">{{ k.strike_count }}</span>
                </div>

                <!-- Cooldown -->
                <div v-if="k.cooldown_until" class="flex-1 min-w-32">
                  <div class="flex items-center justify-between text-[11px] mb-1">
                    <span class="text-error font-semibold">Cooldown</span>
                    <span class="text-error font-mono font-bold">{{ cooldownRemaining(k.cooldown_until) }}</span>
                  </div>
                  <NProgress
                    type="line"
                    :percentage="cooldownProgress(k.cooldown_until)"
                    :height="5"
                    :border-radius="3"
                    :fill-border-radius="3"
                    :show-indicator="false"
                    :processing="true"
                    :rail-color="'#2e2e42'"
                    :fill-color="'#f85149'"
                  />
                </div>
              </div>
            </div>
          </div>
        </NCard>
        </div>

        <!-- Global empty state -->
        <NEmpty v-if="!platforms.length" description="No platforms configured." />
      </template>
    </div>
  </div>
</template>