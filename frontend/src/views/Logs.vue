<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NDataTable, NButton, NInput, NSelect, NPagination, NTag, NModal, NSpin, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import api from '../api'

const loading = ref(false)
const message = useMessage()
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const modelSearch = ref('')
const rows = ref<any[]>([])
const detail = ref<any>(null)
const detailShow = ref(false)
const showDetail = (r: any) => { detail.value = r; detailShow.value = true }

const statusOptions = [
  { label: 'All Status', value: '' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
]

const columns = [
  { title: 'ID', key: 'id', width: 55 },
  { title: 'Time', key: 'created_at', width: 170,
    render: (r: any) => h('span', { class: 'text-[12px] text-text-secondary' }, r.created_at?.replace('T', ' ').slice(0, 19)) },
  { title: 'Pool', key: 'model', width: 90,
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-primary' }, r.model) },
  { title: 'Upstream Model', key: 'upstream_model', width: 200,
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-secondary' }, r.upstream_model || '—') },
  { title: 'Status', key: 'status', width: 85,
    render: (r: any) => r.status === 'success'
      ? h(NTag, { type: 'success', size: 'small', round: true }, { default: () => 'Success' })
      : h(NTag, { type: 'error', size: 'small', round: true }, { default: () => 'Failed' }) },
  { title: 'Tokens', key: 'total_tokens', width: 105,
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-secondary' },
      `${r.prompt_tokens || 0}+${r.completion_tokens || 0}=${r.total_tokens || 0}`) },
  { title: 'Latency', key: 'latency_ms', width: 78,
    render: (r: any) => h('span', { class: 'font-mono text-[12px]' }, `${Math.round(r.latency_ms)}ms`) },
  { title: 'TTFT', key: 'ttft_ms', width: 78,
    render: (r: any) => h('span', { class: 'font-mono text-[12px]' }, `${Math.round(r.ttft_ms)}ms`) },
  { title: 'Actions', key: 'actions', width: 65,
    render: (r: any) => h(NButton, { size: 'tiny', onClick: () => showDetail(r) }, { default: () => 'Detail' }) },
]

async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (modelSearch.value) params.model = modelSearch.value
    const resp = (await api.get('/admin/logs', { params })).data
    rows.value = resp.items
    total.value = resp.total
  } catch (e: any) { message.error('加载失败: ' + (e?.message || '未知错误')); console.error(e) }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Monitoring' }, { label: 'Logs', active: true }]" />

    <div class="p-6 flex flex-col gap-5">
      <div>
        <h1 class="text-[20px] font-semibold text-text-primary">Request Logs</h1>
        <p class="text-sm text-text-secondary mt-0.5">Detailed request history with latency and token metrics</p>
      </div>

      <!-- Filters -->
      <div class="flex items-center gap-3 flex-wrap">
        <NInput v-model:value="modelSearch" placeholder="Filter by model..." clearable style="width:220px" @keyup.enter="page=1;load()" />
        <NSelect v-model:value="statusFilter" :options="statusOptions" style="width:150px" @update:value="page=1;load()" />
        <NButton @click="page=1;load()">Search</NButton>
      </div>

      <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable :columns="columns" :data="rows" :loading="loading" :bordered="false" :pagination="false" />
        <NSpin v-if="loading" class="absolute inset-0 flex items-center justify-center" />
        <div v-if="!loading && rows.length === 0" class="flex flex-col items-center py-12 text-text-secondary">
          <span class="material-symbols-outlined text-[40px] mb-3 opacity-40">receipt_long</span>
          <p class="text-sm">No logs yet. Make some API requests to see them here.</p>
        </div>
      </div>

      <div v-if="total > pageSize" class="flex justify-end">
        <NPagination v-model:page="page" :page-size="pageSize" :total="total" @update:page="load" />
      </div>
    </div>

    <!-- Detail Modal -->
    <NModal v-model:show="detailShow" preset="card" title="Request Detail" style="width:640px">
      <div v-if="detail" class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div class="text-text-secondary">ID</div><div class="font-mono text-[12px]">{{ detail.id }}</div>
        <div class="text-text-secondary">Request ID</div><div class="font-mono text-[11px] break-all">{{ detail.request_id }}</div>
        <div class="text-text-secondary">Pool</div><div class="font-mono text-[12px] text-primary">{{ detail.model }}</div>
        <div class="text-text-secondary">Upstream Model</div><div class="font-mono text-[12px]">{{ detail.upstream_model || '—' }}</div>
        <div class="text-text-secondary">Pool Name</div><div class="font-mono text-[12px]">{{ detail.pool_name || detail.model }}</div>
        <div class="text-text-secondary">Status</div><div :class="detail.status === 'success' ? 'text-success' : 'text-error'">{{ detail.status }}</div>
        <div class="text-text-secondary">Prompt Tokens</div><div class="font-mono">{{ detail.prompt_tokens }}</div>
        <div class="text-text-secondary">Completion Tokens</div><div class="font-mono">{{ detail.completion_tokens }}</div>
        <div class="text-text-secondary">Total Tokens</div><div class="font-mono font-bold">{{ detail.total_tokens }}</div>
        <div class="text-text-secondary">Latency</div><div class="font-mono">{{ Math.round(detail.latency_ms) }}ms</div>
        <div class="text-text-secondary">TTFT</div><div class="font-mono">{{ Math.round(detail.ttft_ms) }}ms</div>
        <div class="text-text-secondary">IP</div><div>{{ detail.ip_address || '—' }}</div>
        <div class="text-text-secondary">Stream</div><div>{{ detail.is_stream ? 'Yes' : 'No' }}</div>
        <div class="text-text-secondary col-span-2">Error Message</div>
        <div class="col-span-2 font-mono text-[12px] text-error" style="word-break:break-all">{{ detail.error_message || '—' }}</div>
      </div>
    </NModal>
  </div>
</template>