<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NButton, NModal, NForm, NFormItem, NInput, NSwitch, NTag,
  NDataTable, NEmpty, NSpin, useMessage,
} from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import { platformsAPI } from '../api'

const message = useMessage()
const loading = ref(false)
const platforms = ref<any[]>([])
const showPlatformModal = ref(false)
const editingPlatformId = ref<number | null>(null)
const platformForm = ref({
  name: '',
  base_url: '',
  models: '',
  is_paid: false,
  is_active: true,
})

// Key modal
const showKeyModal = ref(false)
const editingKeyId = ref<number | null>(null)
const currentPlatformId = ref<number | null>(null)
const keyForm = ref({
  label: '',
  api_key: '',
  enabled: true,
})

const keyColumns = [
  {
    title: 'Label',
    key: 'label',
    width: 80,
    render: (r: any) => h(NTag, { size: 'small', round: true, type: 'info' }, { default: () => `key-${r.label}` }),
  },
  {
    title: 'API Key',
    key: 'api_key',
    render: (r: any) => h('span', {
      class: 'font-mono text-[12px] text-text-secondary',
    }, r.api_key.slice(0, 16) + '***'),
  },
  {
    title: 'Enabled',
    key: 'enabled',
    render: (r: any) => h(NTag, r.enabled
      ? { type: 'success', size: 'small', round: true }
      : { type: 'default', size: 'small', round: true },
    { default: () => r.enabled ? 'Enabled' : 'Disabled' }),
  },
  {
    title: 'Active',
    key: 'is_active',
    render: (r: any) => h(NTag, r.is_active
      ? { type: 'success', size: 'small', round: true }
      : { type: 'warning', size: 'small', round: true },
    { default: () => r.is_active ? 'Active' : 'Inactive' }),
  },
  {
    title: 'Actions',
    key: 'actions',
    width: 120,
    render: (r: any) => [
      h(NButton, { size: 'tiny', onClick: () => openEditKey(r) }, { default: () => 'Edit' }),
      h(NButton, {
        size: 'tiny',
        onClick: () => toggleKeyEnabled(r),
        style: { marginLeft: '6px', color: r.enabled ? '#D03050' : '#18A058' },
      }, { default: () => r.enabled ? 'Disable' : 'Enable' }),
      h(NButton, {
        size: 'tiny', onClick: () => handleDeleteKey(r),
        style: { marginLeft: '6px', color: '#D03050' },
      }, { default: () => 'Del' }),
    ],
  },
]

async function load() {
  loading.value = true
  try {
    platforms.value = (await platformsAPI.list()).data
    // Also fetch detail for each platform to get platform_keys
    await Promise.all(platforms.value.map(async (p: any) => {
      const detail = (await platformsAPI.get(p.id)).data
      p.platform_keys = detail.platform_keys || []
    }))
  } catch (e: any) {
    message.error('加载失败: ' + (e?.message || '未知错误'))
    console.error(e)
  } finally {
    loading.value = false
  }
}

// Platform CRUD
function openAddPlatform() {
  editingPlatformId.value = null
  platformForm.value = { name: '', base_url: '', models: '', is_paid: false, is_active: true }
  showPlatformModal.value = true
}
function openEditPlatform(r: any) {
  editingPlatformId.value = r.id
  platformForm.value = {
    name: r.name,
    base_url: r.base_url,
    models: (r.models || []).join(', '),
    is_paid: r.is_paid,
    is_active: r.is_active,
  }
  showPlatformModal.value = true
}
async function handleSavePlatform() {
  if (!platformForm.value.name || !platformForm.value.base_url) return message.warning('Name 和 Base URL 必填')
  const payload = {
    ...platformForm.value,
    models: platformForm.value.models.split(',').map((s: string) => s.trim()).filter(Boolean),
  }
  if (editingPlatformId.value) {
    await platformsAPI.update(editingPlatformId.value, payload)
  } else {
    await platformsAPI.create(payload)
  }
  showPlatformModal.value = false
  load()
}

// Key CRUD
function openAddKey(platform: any) {
  editingKeyId.value = null
  currentPlatformId.value = platform.id
  keyForm.value = { label: '', api_key: '', enabled: true }
  showKeyModal.value = true
}
function openEditKey(key: any) {
  editingKeyId.value = key.id
  currentPlatformId.value = key.platform_id
  keyForm.value = {
    label: key.label,
    api_key: key.api_key,
    enabled: key.enabled,
  }
  showKeyModal.value = true
}
async function handleSaveKey() {
  if (!keyForm.value.label || !keyForm.value.api_key) return message.warning('Label 和 API Key 必填')
  const payload = {
    label: keyForm.value.label,
    api_key: keyForm.value.api_key,
    enabled: keyForm.value.enabled,
  }
  if (editingKeyId.value) {
    await platformsAPI.updateKey(currentPlatformId.value!, editingKeyId.value, payload)
  } else {
    await platformsAPI.addKey(currentPlatformId.value!, payload)
  }
  showKeyModal.value = false
  load()
}
async function handleDeleteKey(key: any) {
  await platformsAPI.deleteKey(key.platform_id, key.id)
  load()
}
async function handleDeletePlatform(platform: any) {
  try {
    await platformsAPI.delete(platform.id)
    message.success(`Platform "${platform.name}" deleted`)
    load()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || 'Unknown error'
    message.error(`Delete failed: ${detail}`)
  }
}
async function toggleKeyEnabled(key: any) {
  await platformsAPI.updateKey(key.platform_id, key.id, { enabled: !key.enabled })
  load()
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Routing' }, { label: 'Platforms', active: true }]">
      <template #actions>
        <NButton type="primary" size="small" @click="openAddPlatform">+ Add Platform</NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <!-- Header -->
      <div>
        <div>
          <h1 class="text-[20px] font-semibold text-text-primary">Upstream Platforms</h1>
          <p class="text-sm text-text-secondary mt-0.5">
            Manage AI platform vendors and their API keys. Each platform can have multiple keys for load balancing and failover.
          </p>
        </div>
      </div>

      <!-- Loading spinner -->
      <NSpin v-if="loading" class="self-center py-16" size="large" />

      <!-- Platforms list -->
      <template v-if="!loading && platforms.length">
        <div v-for="platform in platforms" :key="platform.id" class="border border-border rounded-xl overflow-hidden bg-surface-container">
          <!-- Platform header -->
          <div class="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface-container-low">
            <span class="font-mono text-[11px] text-text-secondary">#{{ platform.id }}</span>
            <span class="font-semibold text-sm text-text-primary">{{ platform.name }}</span>
            <span class="font-mono text-[11px] text-text-secondary truncate max-w-[200px]" :title="platform.base_url">
              {{ platform.base_url }}
            </span>
            <NTag size="tiny" :type="platform.is_paid ? 'warning' : 'default'" round>
              {{ platform.is_paid ? 'Paid' : 'Free' }}
            </NTag>
            <NTag size="tiny" :type="platform.is_active ? 'success' : 'warning'" round>
              {{ platform.is_active ? 'Active' : 'Disabled' }}
            </NTag>
            <div class="ml-auto flex items-center gap-2">
              <span class="text-xs text-text-secondary font-mono">{{ platform.platform_keys?.length || 0 }} key(s)</span>
              <NButton size="tiny" type="primary" @click="openAddKey(platform)">+ Add Key</NButton>
              <NButton size="tiny" @click="openEditPlatform(platform)">Edit</NButton>
              <NButton size="tiny" color="#D03050" @click="handleDeletePlatform(platform)">Del</NButton>
            </div>
          </div>

          <!-- Keys table -->
          <div class="px-4 py-3" v-if="platform.platform_keys?.length">
            <div class="text-[11px] text-text-secondary mb-2 font-semibold uppercase tracking-wide">API Keys</div>
            <NDataTable
              :columns="keyColumns"
              :data="platform.platform_keys"
              :bordered="false"
              :pagination="false"
              :row-class-name="() => 'hover:bg-surface-container/50 transition-colors'"
              size="small"
            />
          </div>
          <div v-else class="px-4 py-6 text-center text-text-secondary text-sm">
            No API keys. Add one to enable routing.
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <NEmpty v-if="!loading && !platforms.length" description="No platforms configured.">
        <template #extra>
          <NButton type="primary" size="small" @click="openAddPlatform">+ Add Platform</NButton>
        </template>
      </NEmpty>
    </div>

    <!-- Add / Edit Platform Modal -->
    <NModal v-model:show="showPlatformModal" preset="card"
      :title="editingPlatformId ? 'Edit Platform' : 'Add Platform'"
      style="width:500px">
      <NForm label-placement="top">
        <NFormItem label="Platform Name">
          <NInput v-model:value="platformForm.name" placeholder="e.g. NVIDIA NIM" />
        </NFormItem>
        <NFormItem label="Base URL">
          <NInput v-model:value="platformForm.base_url" placeholder="https://integrate.api.nvidia.com/v1" />
        </NFormItem>
        <NFormItem label="Supported Models (comma-separated)">
          <NInput v-model:value="platformForm.models" placeholder="gpt-4o, gpt-4o-mini" />
        </NFormItem>
        <NFormItem label="Billing Tier">
          <div class="flex items-center gap-3">
            <NSwitch v-model:value="platformForm.is_paid" />
            <span class="text-sm text-text-secondary">
              {{ platformForm.is_paid ? 'Paid (tokens count toward cost tracking)' : 'Free (no cost tracking)' }}
            </span>
          </div>
        </NFormItem>
        <NFormItem label="Active">
          <div class="flex items-center gap-3">
            <NSwitch v-model:value="platformForm.is_active" />
            <span class="text-sm text-text-secondary">
              {{ platformForm.is_active ? 'Platform is active' : 'Platform is disabled' }}
            </span>
          </div>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3">
          <NButton @click="showPlatformModal = false">Cancel</NButton>
          <NButton type="primary" @click="handleSavePlatform">
            {{ editingPlatformId ? 'Save Changes' : 'Add Platform' }}
          </NButton>
        </div>
      </template>
    </NModal>

    <!-- Add / Edit Key Modal -->
    <NModal v-model:show="showKeyModal" preset="card"
      :title="editingKeyId ? 'Edit API Key' : 'Add API Key'"
      style="width:480px">
      <NForm label-placement="top">
        <NFormItem label="Key Label (for identification)">
          <NInput v-model:value="keyForm.label" placeholder="e.g. 1, 2, 3 or production-1" />
        </NFormItem>
        <NFormItem label="API Key">
          <NInput
            v-model:value="keyForm.api_key"
            type="password"
            show-password-on="mousedown"
            placeholder="nvapi-..."
          />
        </NFormItem>
        <NFormItem label="Enabled">
          <div class="flex items-center gap-3">
            <NSwitch v-model:value="keyForm.enabled" />
            <span class="text-sm text-text-secondary">
              {{ keyForm.enabled ? 'Key is enabled for routing' : 'Key is disabled' }}
            </span>
          </div>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3">
          <NButton @click="showKeyModal = false">Cancel</NButton>
          <NButton type="primary" @click="handleSaveKey">
            {{ editingKeyId ? 'Save Changes' : 'Add Key' }}
          </NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>