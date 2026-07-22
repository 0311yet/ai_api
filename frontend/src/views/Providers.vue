<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NDataTable, NButton, NModal, NForm, NFormItem, NInput, NSwitch, NTag, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const rows = ref<any[]>([])
const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', base_url: '', api_key: '', models: '', is_active: true })

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  {
    title: 'Name', key: 'name',
    render: (r: any) => h('span', { class: 'font-semibold text-sm text-text-primary' }, r.name),
  },
  {
    title: 'Base URL', key: 'base_url',
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-secondary truncate block', title: r.base_url }, r.base_url),
  },
  {
    title: 'API Key', key: 'api_key',
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-secondary' }, r.api_key.slice(0, 12) + '***'),
  },
  {
    title: 'Models', key: 'models',
    render: (r: any) => h(NTag, { size: 'small', round: true }, { default: () => r.models?.length || 0 }),
  },
  {
    title: 'Status', key: 'is_active',
    render: (r: any) => h(NTag, r.is_active ? { type: 'success', size: 'small', round: true } : { type: 'warning', size: 'small', round: true }, { default: () => r.is_active ? 'Active' : 'Degraded' }),
  },
  { title: 'Created', key: 'created_at', render: (r: any) => r.created_at?.slice(0, 10) },
  {
    title: 'Actions', key: 'actions', width: 180,
    render: (r: any) => [
      h(NButton, { size: 'tiny', onClick: () => openEdit(r) }, { default: () => 'Edit' }),
      h(NButton, {
        size: 'tiny', onClick: () => toggleActive(r),
        style: { marginLeft: '8px', color: r.is_active ? '#D03050' : '#18A058' }
      }, { default: () => r.is_active ? 'Disable' : 'Enable' }),
      h(NButton, { size: 'tiny', onClick: () => handleDelete(r.id), style: { marginLeft: '8px' } }, { default: () => 'Del' }),
    ],
  },
]

async function load() {
  loading.value = true
  try { rows.value = (await api.get('/admin/providers')).data }
  catch (e: any) { message.error('加载失败: ' + (e?.message || '未知错误')); console.error(e) }
  finally { loading.value = false }
}

function openAdd() {
  editingId.value = null
  form.value = { name: '', base_url: '', api_key: '', models: '', is_active: true }
  showModal.value = true
}
function openEdit(r: any) {
  editingId.value = r.id
  form.value = { name: r.name, base_url: r.base_url, api_key: r.api_key, models: (r.models || []).join(', '), is_active: r.is_active }
  showModal.value = true
}
async function handleSave() {
  if (!form.value.name || !form.value.base_url) return message.warning('Name 和 Base URL 必填')
  const payload = { ...form.value, models: form.value.models.split(',').map((s: string) => s.trim()).filter(Boolean) }
  if (editingId.value) await api.put(`/admin/providers/${editingId.value}`, payload)
  else await api.post('/admin/providers', payload)
  showModal.value = false; load()
}
async function handleDelete(id: number) {
  await api.delete(`/admin/providers/${id}`)
  load()
}
async function toggleActive(r: any) {
  await api.put(`/admin/providers/${r.id}`, { is_active: !r.is_active })
  load()
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Routing' }, { label: 'Providers', active: true }]">
      <template #actions>
        <NButton type="primary" size="small" @click="openAdd">+ Add Provider</NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-[20px] font-semibold text-text-primary">Upstream Providers</h1>
          <p class="text-sm text-text-secondary mt-0.5">Manage upstream AI providers and their configurations</p>
        </div>
      </div>

      <!-- Table -->
      <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable :columns="columns" :data="rows" :loading="loading" :bordered="false" :pagination="false" />
        <div v-if="!loading && rows.length === 0" class="flex flex-col items-center py-12 text-text-secondary">
          <span class="material-symbols-outlined text-[40px] mb-3 opacity-40">cloud_off</span>
          <p class="text-sm">No providers configured. Click "Add Provider" to get started.</p>
        </div>
      </div>
    </div>

    <!-- Add / Edit Modal -->
    <NModal v-model:show="showModal" preset="card" :title="editingId ? 'Edit Provider' : 'Add Provider'" style="width:480px">
      <NForm label-placement="top">
        <NFormItem label="Provider Name"><NInput v-model:value="form.name" placeholder="e.g. OpenAI-Mock" /></NFormItem>
        <NFormItem label="Base URL"><NInput v-model:value="form.base_url" placeholder="https://api.openai.com/v1" /></NFormItem>
        <NFormItem label="API Key"><NInput v-model:value="form.api_key" type="password" show-password-on="mousedown" placeholder="sk-..." /></NFormItem>
        <NFormItem label="Supported Models (comma-separated)"><NInput v-model:value="form.models" placeholder="gpt-4o, gpt-4o-mini" /></NFormItem>
        <NFormItem label="Active">
          <div class="flex items-center gap-3">
            <NSwitch v-model:value="form.is_active" />
            <span class="text-sm text-text-secondary">{{ form.is_active ? 'Provider is active' : 'Provider is disabled' }}</span>
          </div>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3">
          <NButton @click="showModal = false">Cancel</NButton>
          <NButton type="primary" @click="handleSave">{{ editingId ? 'Save Changes' : 'Add Provider' }}</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>