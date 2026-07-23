<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NDataTable, NButton, NModal, NForm, NFormItem, NInput, NSelect, NSwitch, NTag, NInputNumber, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import api from '../api'
import { platformsAPI } from '../api'

const message = useMessage()
const loading = ref(false)
const rows = ref<any[]>([])
const platforms = ref<any[]>([])  // 新架构: Platforms
const showPoolModal = ref(false)
const showConfigModal = ref(false)
const editingPoolId = ref<number | null>(null)
const configPool = ref<any>(null)
const poolForm = ref({ name: '', display_name: '', strategy: 'priority', is_active: true })
const strategies = [
  { label: 'Priority (优先级回退)', value: 'priority' },
  { label: 'Round Robin (轮询)', value: 'round_robin' },
  { label: 'Weighted (加权随机)', value: 'weighted' },
  { label: 'Random (随机)', value: 'random' },
]
const strategyTag: Record<string, { color: string; icon: string }> = {
  priority: { color: 'info', icon: 'sort' },
  round_robin: { color: 'default', icon: 'cycle' },
  weighted: { color: 'warning', icon: 'call_split' },
  random: { color: 'default', icon: 'shuffle' },
}

// Config Modal state
const configItems = ref<any[]>([])
const showAddItemModal = ref(false)
const itemForm = ref({ platform_id: null as number | null, model: '', priority: 1, weight: 1, is_active: true })


const poolColumns = [
  { title: 'Pool ID', key: 'name', width: 130,
    render: (r: any) => h('span', { class: 'font-mono text-[13px] text-text-primary' }, r.name) },
  { title: 'Display Name', key: 'display_name' },
  { title: 'Strategy', key: 'strategy', width: 160,
    render: (r: any) => {
      const s = strategyTag[r.strategy] || strategyTag.priority
      return h(NTag, { type: s.color as any, size: 'small', round: true }, {
        default: () => h('span', { class: 'flex items-center gap-1' }, [
          h('span', { class: 'material-symbols-outlined text-[12px]' }, s.icon),
          r.strategy,
        ]),
      })
    },
  },
  { title: 'Models', key: 'items', width: 90, align: 'center' as const,
    render: (r: any) => h('span', {
      class: 'inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 font-mono text-[13px] text-text-primary bg-surface-bright rounded border border-border'
    }, r.items?.length || 0) },
  { title: 'Status', key: 'is_active', width: 110,
    render: (r: any) => h(NTag, r.is_active
      ? { type: 'success', size: 'small', round: true }
      : { type: 'warning', size: 'small', round: true },
    { default: () => r.is_active ? 'Enabled' : 'Disabled' }) },
  { title: 'Actions', key: 'actions', width: 220,
    render: (r: any) => [
      h(NButton, { size: 'tiny', type: 'primary', onClick: () => openConfig(r) }, { default: () => 'Config Models' }),
      h(NButton, { size: 'tiny', onClick: () => openEdit(r), style: { marginLeft: '8px' } }, { default: () => 'Edit' }),
      h(NButton, { size: 'tiny', onClick: () => handleDelete(r.id), style: { marginLeft: '8px' } }, { default: () => 'Del' }),
    ],
  },
]

const itemColumns = [
  { title: '#', key: 'priority', width: 60, align: 'center' as const,
    render: (_: any, i: number) => h('span', {
      class: 'inline-flex items-center justify-center w-6 h-6 font-mono text-[13px] bg-surface-container border border-border rounded'
    }, i + 1) },
  { title: 'Platform', key: 'platform_name',
    render: (r: any) => h('div', { class: 'flex items-center gap-1.5' }, [
      h('span', { class: 'font-semibold text-sm text-text-primary' }, r.platform_name || `Platform #${r.platform_id}`),
      r.key_label ? h(NTag, { size: 'tiny', round: true, type: 'info' }, { default: () => `key-${r.key_label}` }) : null
    ].filter(Boolean)) },
  { title: 'Model Name', key: 'model', render: (r: any) => h('span', { class: 'font-mono text-[13px] text-text-secondary' }, r.model) },
  { title: 'Weight', key: 'weight', width: 80, align: 'center' as const,
    render: (r: any) => h('span', { class: 'font-mono text-[13px]' }, r.weight) },
  { title: 'Status', key: 'is_active', width: 90,
    render: (r: any) => h(NTag, r.is_active ? { type: 'success', size: 'small', round: true } : { type: 'default', size: 'small', round: true }, { default: () => r.is_active ? 'Active' : 'Standby' }) },
  { title: '', key: 'actions', width: 60,
    render: (r: any) => h(NButton, { size: 'tiny', onClick: () => removeItem(r) }, {
      default: () => h('span', { class: 'material-symbols-outlined text-[16px]', style: 'color:#D03050' }, 'remove_circle_outline'),
    }) },
]

async function load() {
  loading.value = true
  try {
    const poolsRes = await api.get('/admin/pools')
    rows.value = poolsRes.data
    platforms.value = (await platformsAPI.list()).data
    // Also fetch detail to get platform_keys for each platform
    await Promise.all(platforms.value.map(async (p: any) => {
      const detail = (await platformsAPI.get(p.id)).data
      p.platform_keys = detail.platform_keys || []
    }))
  } catch (e: any) { message.error('加载失败: ' + (e?.message || '未知错误')); console.error(e) }
  finally { loading.value = false }
}

function openAdd() { editingPoolId.value = null; poolForm.value = { name: '', display_name: '', strategy: 'priority', is_active: true }; showPoolModal.value = true }
function openEdit(r: any) { editingPoolId.value = r.id; poolForm.value = { name: r.name, display_name: r.display_name || '', strategy: r.strategy, is_active: r.is_active }; showPoolModal.value = true }
async function openConfig(r: any) {
  configPool.value = r
  configItems.value = [...(r.items || [])]
  showConfigModal.value = true
}
async function handleSavePool() {
  if (!poolForm.value.name) return message.warning('Pool name 必填')
  if (editingPoolId.value) await api.put(`/admin/pools/${editingPoolId.value}`, poolForm.value)
  else await api.post('/admin/pools', poolForm.value)
  showPoolModal.value = false; load()
}
async function handleDelete(id: number) { await api.delete(`/admin/pools/${id}`); load() }

// Add item to pool
function openAddItem() {
  itemForm.value = { platform_id: null, model: '', priority: 1, weight: 1, is_active: true }
  showAddItemModal.value = true
}
async function handleAddItem() {
  if (!itemForm.value.platform_id || !itemForm.value.model) return message.warning('Platform 和 Model 必填')
  await api.post(`/admin/pools/${configPool.value.id}/items`, {
    platform_id: itemForm.value.platform_id,
    model: itemForm.value.model,
    priority: itemForm.value.priority,
    weight: itemForm.value.weight,
    is_active: itemForm.value.is_active,
  })
  showAddItemModal.value = false
  const updated = (await api.get(`/admin/pools/${configPool.value.id}`)).data
  configPool.value = updated
  configItems.value = [...(updated.items || [])]
}
async function removeItem(item: any) {
  await api.delete(`/admin/pools/${configPool.value.id}/items/${item.id}`)
  const updated = (await api.get(`/admin/pools/${configPool.value.id}`)).data
  configPool.value = updated
  configItems.value = [...(updated.items || [])]
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Routing' }, { label: 'Pools', active: true }]">
      <template #actions>
        <NButton type="primary" size="small" @click="openAdd">+ Add Model Pool</NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <div>
        <h1 class="text-[20px] font-semibold text-text-primary">Model Pools</h1>
        <p class="text-sm text-text-secondary mt-0.5">Manage fallback strategies, load balancing, and routing priorities</p>
      </div>

      <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable :columns="poolColumns" :data="rows" :loading="loading" :bordered="false" :pagination="false" />
        <div v-if="!loading && rows.length === 0" class="flex flex-col items-center py-12 text-text-secondary">
          <span class="material-symbols-outlined text-[40px] mb-3 opacity-40">database</span>
          <p class="text-sm">No pools configured. Add a pool to start routing requests.</p>
        </div>
      </div>
    </div>

    <!-- Add/Edit Pool Modal -->
    <NModal v-model:show="showPoolModal" preset="card" :title="editingPoolId ? 'Edit Pool' : 'Add Pool'" style="width:440px">
      <NForm label-placement="top">
        <NFormItem label="Pool Name (客户端调用的 model 名)"><NInput v-model:value="poolForm.name" placeholder="gpt-4o" :disabled="!!editingPoolId" /></NFormItem>
        <NFormItem label="Display Name"><NInput v-model:value="poolForm.display_name" placeholder="GPT-4o All-in-one" /></NFormItem>
        <NFormItem label="Routing Strategy"><NSelect v-model:value="poolForm.strategy" :options="strategies" /></NFormItem>
        <NFormItem label="Active"><NSwitch v-model:value="poolForm.is_active" /></NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3"><NButton @click="showPoolModal=false">Cancel</NButton><NButton type="primary" @click="handleSavePool">Save</NButton></div>
      </template>
    </NModal>

    <!-- Config Models Modal -->
    <NModal v-model:show="showConfigModal" preset="card" :title="`Configure Routing: ${configPool?.name}`" style="width:820px">
      <div class="mb-4 flex justify-end">
        <NButton size="small" @click="openAddItem">+ Add Target Model</NButton>
      </div>

      <!-- Items table -->
      <div class="border border-border rounded-lg overflow-hidden bg-background">
        <NDataTable :columns="itemColumns" :data="configItems" :bordered="false" :pagination="false" :row-class-name="() => 'hover:bg-surface-container/50 transition-colors'" />
        <div v-if="configItems.length === 0" class="flex flex-col items-center py-8 text-text-secondary">
          <p class="text-sm">No models configured. Add a target model above.</p>
        </div>
      </div>

      <!-- Routing info box -->
      <div class="mt-4 p-4 rounded-lg bg-info/5 border border-info/20 flex gap-3">
        <span class="material-symbols-outlined text-info shrink-0">info</span>
        <p class="text-[12px] text-text-secondary leading-relaxed">
          Priority routing evaluates models in order. If a request fails or times out, it falls back to the next priority.
          Weights are applied only if multiple models share the exact same priority level (Round Robin).
          Each pool item can optionally specify a Platform Key; if not specified, all enabled keys under that platform are used.
        </p>
      </div>

      <template #footer>
        <div class="flex justify-end"><NButton @click="showConfigModal=false">Close</NButton></div>
      </template>
    </NModal>

    <!-- Add Item Modal -->
    <NModal v-model:show="showAddItemModal" preset="card" title="Add Target Model" style="width:440px">
      <NForm label-placement="top">
        <NFormItem label="Platform">
          <NSelect v-model:value="itemForm.platform_id" :options="platforms.map((p:any) => ({label: p.name, value: p.id, disabled: !p.is_active}))" placeholder="Select platform" />
        </NFormItem>
        <NFormItem label="Model Name"><NInput v-model:value="itemForm.model" placeholder="e.g. gpt-4o, deepseek-v4-pro" /></NFormItem>
        <NFormItem label="Priority (1 = highest)"><NInputNumber v-model:value="itemForm.priority" :min="1" /></NFormItem>
        <NFormItem label="Weight"><NInputNumber v-model:value="itemForm.weight" :min="0" /></NFormItem>
        <NFormItem label="Active"><NSwitch v-model:value="itemForm.is_active" /></NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3"><NButton @click="showAddItemModal=false">Cancel</NButton><NButton type="primary" @click="handleAddItem">Add</NButton></div>
      </template>
    </NModal>
  </div>
</template>