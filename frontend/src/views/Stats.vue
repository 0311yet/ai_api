<script setup lang="ts">
import { ref, onMounted, h, computed } from 'vue'
import { NDataTable, NSpin, NSelect, useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import TopBar from '../components/TopBar.vue'
import api from '../api'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const loading = ref(false)
const message = useMessage()
const timeseries = ref<any[]>([])
const byModel = ref<any[]>([])
const chartDays = ref(30)
const dayOptions = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
]

onMounted(async () => { await load() })

async function load() {
  loading.value = true
  try {
    const [ts, md] = await Promise.all([
      api.get(`/admin/stats/timeseries?days=${chartDays.value}`),
      api.get('/admin/stats/by-model'),
    ])
    timeseries.value = ts.data
    byModel.value = md.data
  } catch (e: any) { message.error('加载失败: ' + (e?.message || '未知错误')); console.error(e) }
  finally { loading.value = false }
}

const tsColumns = [
  { title: 'Date', key: 'date', width: 120 },
  { title: 'Requests', key: 'requests', render: (r: any) => h('span', { class: 'font-mono' }, r.requests) },
  {
    title: 'Success', key: 'success',
    render: (r: any) => h('span', { class: 'text-success font-mono' }, r.success),
  },
  {
    title: 'Failed', key: 'failed',
    render: (r: any) => h('span', { class: 'text-error font-mono' }, r.failed),
  },
  { title: 'Total Tokens', key: 'total_tokens',
    render: (r: any) => h('span', { class: 'font-mono' }, r.total_tokens.toLocaleString()) },
  { title: 'Avg Latency', key: 'avg_latency_ms',
    render: (r: any) => h('span', { class: 'font-mono' }, `${Math.round(r.avg_latency_ms)}ms`) },
  { title: 'Avg TTFT', key: 'avg_ttft_ms',
    render: (r: any) => h('span', { class: 'font-mono text-warning' }, `${Math.round(r.avg_ttft_ms)}ms`) },
]

const modelColumns = [
  { title: 'Model', key: 'model', render: (r: any) => h('span', { class: 'font-mono text-[13px]' }, r.model) },
  { title: 'Requests', key: 'request_count', render: (r: any) => h('span', { class: 'font-mono' }, r.request_count) },
  { title: 'Success', key: 'success_count', render: (r: any) => h('span', { class: 'text-success font-mono' }, r.success_count) },
  { title: 'Total Tokens', key: 'total_tokens',
    render: (r: any) => h('span', { class: 'font-mono font-bold' }, r.total_tokens.toLocaleString()) },
  { title: 'Avg Latency', key: 'avg_latency_ms',
    render: (r: any) => h('span', { class: 'font-mono' }, `${Math.round(r.avg_latency_ms)}ms`) },
]

// Model bar chart
const modelChartOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#1f1e2a', borderColor: '#2e2e42', textStyle: { color: '#e3e0f1' } },
  grid: { left: 80, right: 16, top: 16, bottom: 40 },
  xAxis: { type: 'category', data: byModel.value.map((r: any) => r.model), axisLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c', rotate: 30 } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#2e2e42' } }, axisLabel: { color: '#8c8c8c' } },
  series: [{
    name: 'Requests',
    type: 'bar',
    data: byModel.value.map((r: any) => r.request_count),
    itemStyle: { color: '#409eff', borderRadius: [4, 4, 0, 0] },
  }],
}))
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Analytics' }, { label: 'Stats', active: true }]">
      <template #actions>
        <NSelect v-model:value="chartDays" :options="dayOptions" size="small" style="width:140px" @update:value="load()" />
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-6">
      <div>
        <h1 class="text-[20px] font-semibold text-text-primary">Statistics</h1>
        <p class="text-sm text-text-secondary mt-0.5">Request trends and model-level analytics</p>
      </div>

      <NSpin v-if="loading" class="self-center py-16" size="large" />

      <template v-else>
        <!-- Model chart -->
        <div class="bg-surface-container border border-border rounded-xl p-4">
          <div class="text-sm font-semibold text-text-primary mb-3">Requests by Model</div>
          <VChart :option="modelChartOption" style="height:200px" autoresize />
        </div>

        <!-- Daily trend table -->
        <div>
          <div class="text-sm font-semibold text-text-primary mb-3">Daily Request Trend ({{ chartDays }} days)</div>
          <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
            <NDataTable :columns="tsColumns" :data="timeseries" :bordered="false" :pagination="false" />
            <div v-if="timeseries.length === 0" class="flex flex-col items-center py-8 text-text-secondary text-sm">No data for selected range</div>
          </div>
        </div>

        <!-- By model table -->
        <div>
          <div class="text-sm font-semibold text-text-primary mb-3">By Model</div>
          <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
            <NDataTable :columns="modelColumns" :data="byModel" :bordered="false" :pagination="false" />
            <div v-if="byModel.length === 0" class="flex flex-col items-center py-8 text-text-secondary text-sm">No model data yet</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>