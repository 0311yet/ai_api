<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NDataTable, NButton, NModal, NForm, NFormItem, NInput, NSwitch, NTag, useMessage } from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const rows = ref<any[]>([])
const pools = ref<any[]>([])
const showModal = ref(false)
const showKeyModal = ref(false)
const viewingKey = ref('')
const editingId = ref<number | null>(null)
const form = ref({ name: '', pool_id: null as number | null, allowed_models: '', is_active: true })

const columns = [
  { title: 'ID', key: 'id', width: 50 },
  { title: 'Name', key: 'name', render: (r: any) => h('span', { class: 'font-medium text-sm' }, r.name || '—') },
  {
    title: 'Key',
    key: 'key',
    render: (r: any) => h('span', {
      class: 'font-mono text-[12px] text-text-secondary cursor-pointer hover:text-primary',
      title: 'Click to copy',
      onClick: () => copyKey(r.key),
    }, r.key.slice(0, 16) + '...' + r.key.slice(-6)),
  },
  { title: 'Bound Pool', key: 'pool_name', render: (r: any) => r.pool_name ? h(NTag, { size: 'small', round: true }, { default: () => r.pool_name }) : h('span', { class: 'text-text-secondary text-sm' }, '—') },
  { title: 'Status', key: 'is_active', width: 90,
    render: (r: any) => h(NTag, r.is_active ? { type: 'success', size: 'small', round: true } : { type: 'default', size: 'small', round: true }, { default: () => r.is_active ? 'Active' : 'Inactive' }) },
  { title: 'Req', key: 'request_count', width: 70, align: 'center' as const, render: (r: any) => h('span', { class: 'font-mono text-[13px]' }, r.request_count) },
  { title: 'Tokens', key: 'total_tokens', width: 90, align: 'center' as const, render: (r: any) => h('span', { class: 'font-mono text-[13px]' }, r.total_tokens) },
  { title: 'Created', key: 'created_at', width: 110, render: (r: any) => r.created_at?.slice(0, 10) },
  { title: 'Actions', key: 'actions', width: 160,
    render: (r: any) => [
      h(NButton, { size: 'tiny', onClick: () => { viewingKey.value = r.key; showKeyModal.value = true } }, { default: () => 'View Key' }),
      h(NButton, { size: 'tiny', onClick: () => openEdit(r), style: { marginLeft: '8px' } }, { default: () => 'Edit' }),
      h(NButton, { size: 'tiny', onClick: () => handleDelete(r.id), style: { marginLeft: '8px' } }, { default: () => 'Del' }),
    ],
  },
]

async function load() {
  loading.value = true
  try {
    const [keysRes, poolsRes] = await Promise.all([api.get('/admin/keys'), api.get('/admin/pools')])
    rows.value = keysRes.data
    pools.value = poolsRes.data
  } catch (e: any) { message.error('加载失败: ' + (e?.message || '未知错误')); console.error(e) }
  finally { loading.value = false }
}

function openAdd() {
  editingId.value = null
  form.value = { name: '', pool_id: null, allowed_models: '', is_active: true }
  showModal.value = true
}
function openEdit(r: any) {
  editingId.value = r.id
  form.value = { name: r.name || '', pool_id: r.pool_id, allowed_models: (r.allowed_models || []).join(', '), is_active: r.is_active }
  showModal.value = true
}

async function handleSave() {
  const payload = {
    name: form.value.name,
    pool_id: form.value.pool_id,
    allowed_models: form.value.allowed_models.split(',').map((s: string) => s.trim()).filter(Boolean),
    is_active: form.value.is_active,
  }
  if (editingId.value) {
    await api.put(`/admin/keys/${editingId.value}`, payload)
  } else {
    const res = await api.post('/admin/keys', payload)
    viewingKey.value = res.data.key
    showModal.value = false
    showKeyModal.value = true
  }
  showModal.value = false
  load()
}

async function handleDelete(id: number) {
  await api.delete(`/admin/keys/${id}`)
  load()
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key).then(() => message.success('Key copied to clipboard'))
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Security' }, { label: 'Keys', active: true }]">
      <template #actions>
        <NButton type="primary" size="small" @click="openAdd">+ Generate Key</NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <div>
        <h1 class="text-[20px] font-semibold text-text-primary">Key Management</h1>
        <p class="text-sm text-text-secondary mt-0.5">Generate and manage client API keys. Keys are only shown once upon creation.</p>
      </div>

      <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable :columns="columns" :data="rows" :loading="loading" :bordered="false" :pagination="false" />
        <div v-if="!loading && rows.length === 0" class="flex flex-col items-center py-12 text-text-secondary">
          <span class="material-symbols-outlined text-[40px] mb-3 opacity-40">key</span>
          <p class="text-sm">No keys generated yet. Click "Generate Key" to create one.</p>
        </div>
      </div>
    </div>

    <!-- Add/Edit Key Modal -->
    <NModal v-model:show="showModal" preset="card" :title="editingId ? 'Edit Key' : 'Generate New Key'" style="width:480px">
      <NForm label-placement="top">
        <NFormItem label="Key Name"><NInput v-model:value="form.name" placeholder="My App" /></NFormItem>
        <NFormItem label="Bind to Pool">
          <NSelect v-model:value="form.pool_id" :options="[{label:'None',value:null}, ...pools.map((p:any)=>({label:p.display_name||p.name,value:p.id}))]" placeholder="Select pool" clearable />
        </NFormItem>
        <NFormItem label="Allowed Models (comma-separated, empty = all)">
          <NInput v-model:value="form.allowed_models" placeholder="gpt-4o, gpt-4o-mini" />
        </NFormItem>
        <NFormItem label="Active"><NSwitch v-model:value="form.is_active" /></NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3"><NButton @click="showModal=false">Cancel</NButton><NButton type="primary" @click="handleSave">{{ editingId ? 'Save' : 'Generate' }}</NButton></div>
      </template>
    </NModal>

    <!-- View Key Modal -->
    <NModal v-model:show="showKeyModal" preset="card" title="Client Key" style="width:540px">
      <div class="bg-background border border-border rounded-lg p-4">
        <div class="font-mono text-sm text-text-primary break-all leading-relaxed">{{ viewingKey }}</div>
      </div>
      <div class="mt-3 p-3 rounded-lg bg-warning/10 border border-warning/20 flex gap-2">
        <span class="material-symbols-outlined text-warning text-[18px] shrink-0">warning</span>
        <p class="text-[12px] text-text-secondary">请妥善保存此 Key，仅显示一次。丢失后请删除并重新生成。</p>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <NButton @click="copyKey(viewingKey)">Copy</NButton>
          <NButton type="primary" @click="showKeyModal=false; load()">Done</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>