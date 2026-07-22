<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { NSpin, NSelect } from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import TopBar from '../components/TopBar.vue'
import StatCard from '../components/StatCard.vue'
import api from '../api'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

const stats = ref<any>({})
const timeseries = ref<any[]>([])
const loading = ref(false)
const loadError = ref<string>('')
const chartDays = ref(7)
const dayOptions = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
]

onMounted(async () => { await load() })

async function load() {
  loadError.value = ''
  loading.value = true
  try {
    const [s, ts] = await Promise.all([
      api.get('/admin/stats/dashboard'),
      api.get(`/admin/stats/timeseries?days=${chartDays.value}`),
    ])
    stats.value = s.data || {}
    timeseries.value = ts.data || []
  } catch (e: any) {
    loadError.value = e?.message || 'Failed to load data'
    console.error('[Dashboard] load error:', e)
  } finally {
    loading.value = false
  }
}

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

// safe getter for stats (avoids undefined access)
function sv(key: string, fallback = 0) {
  return stats.value?.[key] ?? fallback
}

// Request Trend Chart
const requestTrendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#1f1e2a', borderColor: '#2e2e42', textStyle: { color: '#e3e0f1' } },
  legend: { bottom: 0, textStyle: { color: '#c0c7d4' }, itemWidth: 16 },
  grid: { left: 48, right: 16, top: 16, bottom: 48 },
  xAxis: { type: 'category', data: timeseries.value.map((r: any) => r.date.slice(5)), axisLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  series: [
    { name: 'Total', type: 'line', data: timeseries.value.map((r: any) => r.requests), smooth: true, lineStyle: { color: '#409eff', width: 2 }, itemStyle: { color: '#409eff' } },
    { name: 'Success', type: 'line', data: timeseries.value.map((r: any) => r.success), smooth: true, lineStyle: { color: '#18A058', width: 2 }, itemStyle: { color: '#18A058' } },
    { name: 'Failed', type: 'line', data: timeseries.value.map((r: any) => r.failed), smooth: true, lineStyle: { color: '#D03050', width: 2 }, itemStyle: { color: '#D03050' } },
  ],
}))

// Token Usage Chart (Grouped Bar)
const tokenUsageOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#1f1e2a', borderColor: '#2e2e42', textStyle: { color: '#e3e0f1' } },
  legend: { bottom: 0, textStyle: { color: '#c0c7d4' }, itemWidth: 16 },
  grid: { left: 48, right: 16, top: 16, bottom: 48 },
  xAxis: { type: 'category', data: timeseries.value.map((r: any) => r.date.slice(5)), axisLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  series: [
    { name: 'Prompt', type: 'bar', data: timeseries.value.map((r: any) => r.prompt_tokens), itemStyle: { color: '#6d28d9' }, barWidth: '35%' },
    { name: 'Completion', type: 'bar', data: timeseries.value.map((r: any) => r.completion_tokens), itemStyle: { color: '#a78bfa' }, barWidth: '35%' },
  ],
}))

// Latency Trend
const latencyTrendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#1f1e2a', borderColor: '#2e2e42', textStyle: { color: '#e3e0f1' } },
  legend: { bottom: 0, textStyle: { color: '#c0c7d4' }, itemWidth: 16 },
  grid: { left: 48, right: 16, top: 16, bottom: 48 },
  xAxis: { type: 'category', data: timeseries.value.map((r: any) => r.date.slice(5)), axisLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c', formatter: '{value}ms' } },
  series: [
    { name: 'Latency', type: 'line', data: timeseries.value.map((r: any) => Math.round(r.avg_latency_ms)), smooth: true, lineStyle: { color: '#F0A020', width: 2 }, itemStyle: { color: '#F0A020' } },
    { name: 'TTFT', type: 'line', data: timeseries.value.map((r: any) => Math.round(r.avg_ttft_ms)), smooth: true, lineStyle: { color: '#2080F0', width: 2 }, itemStyle: { color: '#2080F0' } },
  ],
}))
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Dashboard', active: true }]">
      <template #actions>
        <NSelect v-model:value="chartDays" :options="dayOptions" size="small" style="width:130px" @update:value="load()" />
      </template>
    </TopBar>

    <div class="flex-1 p-6 flex flex-col gap-6">
      <NSpin v-if="loading" class="self-center py-16" size="large" />

      <div v-else-if="loadError" class="flex flex-col items-center justify-center py-16 text-center gap-3">
        <div class="text-error text-sm">{{ loadError }}</div>
        <button class="px-4 py-2 bg-primary-container text-white rounded-lg text-sm" @click="load">Retry</button>
      </div>

      <template v-else>
        <!-- Stat Cards: Bento Grid 4 cards -->
        <div class="grid grid-cols-4 gap-4">
          <StatCard label="Total Requests" :value="fmt(sv('total_requests'))" accent-color="info" />
          <StatCard label="Success Rate" :value="sv('success_rate').toFixed(1) + '%'" accent-color="success" />
          <StatCard label="Total Tokens" :value="fmt(sv('total_tokens'))" accent-color="purple" />
          <StatCard label="Avg Latency" :value="Math.round(sv('avg_latency_ms')) + 'ms'" accent-color="orange" />
        </div>

        <!-- Secondary cards -->
        <div class="grid grid-cols-3 gap-4">
          <StatCard label="Avg TTFT" :value="Math.round(sv('avg_ttft_ms')) + 'ms'" accent-color="warning" />
          <StatCard label="Active Keys" :value="String(sv('active_keys'))" accent-color="info" />
          <StatCard label="Active Pools" :value="String(sv('active_pools'))" accent-color="purple" />
        </div>

        <!-- Charts: Bento Grid 3 blocks -->
        <div class="grid grid-cols-3 gap-4">
          <!-- Request Trend -->
          <div class="bg-surface-container border border-border rounded-xl p-4 col-span-2">
            <div class="text-sm font-semibold text-text-primary mb-3">Request Trend</div>
            <VChart :option="requestTrendOption" style="height:220px" autoresize />
          </div>
          <!-- Latency Trend -->
          <div class="bg-surface-container border border-border rounded-xl p-4">
            <div class="text-sm font-semibold text-text-primary mb-3">Latency Trend</div>
            <VChart :option="latencyTrendOption" style="height:220px" autoresize />
          </div>
        </div>

        <!-- Token Usage -->
        <div class="bg-surface-container border border-border rounded-xl p-4">
          <div class="text-sm font-semibold text-text-primary mb-3">Token Usage</div>
          <VChart :option="tokenUsageOption" style="height:200px" autoresize />
        </div>
      </template>
    </div>
  </div>
</template>