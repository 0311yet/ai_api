<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NDataTable, NButton, NModal, NForm, NFormItem, NInputNumber,
  NTag, NSpin, useMessage,
} from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import { ratesAPI } from '../api'

const message = useMessage()
const loading = ref(false)
const rows = ref<any[]>([])

const showModal = ref(false)
const editing = ref<any>(null)
const form = ref({
  input_price: 0,
  output_price: 0,
})

const columns = [
  {
    title: 'Model',
    key: 'model',
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-primary' }, r.model),
  },
  {
    title: 'Status',
    key: 'in_pool',
    width: 120,
    render: (r: any) => h(NTag,
      r.in_pool
        ? { type: 'success', size: 'small', round: true }
        : { type: 'warning', size: 'small', round: true },
      { default: () => r.in_pool ? 'In Pool' : 'Not Routed' }
    ),
  },
  {
    title: 'Billing',
    key: 'is_paid',
    width: 120,
    render: (r: any) => h(NTag,
      r.is_paid
        ? { type: 'warning', size: 'small', round: true }
        : { type: 'default', size: 'small', round: true },
      { default: () => r.is_paid ? 'Paid' : 'Free' }
    ),
  },
  { title: 'Input Price /1M', key: 'input_price', width: 150,
    render: (r: any) => fmtPrice(r.input_price) },
  { title: 'Output Price /1M', key: 'output_price', width: 150,
    render: (r: any) => fmtPrice(r.output_price) },
  {
    title: 'Actions', key: 'actions', width: 100,
    render: (r: any) => [
      h(NButton, { size: 'tiny', onClick: () => openEdit(r), disabled: !r.in_pool },
        { default: () => 'Edit' }),
    ],
  },
]

function fmtPrice(p: number) {
  const v = Number(p) || 0
  return h('span', { class: 'font-mono text-[12px] text-text-primary' }, `$${v.toFixed(4)}`)
}

async function load() {
  loading.value = true
  try {
    rows.value = (await ratesAPI.models()).data
  } catch (e: any) {
    message.error('加载失败: ' + (e?.message || '未知错误'))
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function reloadOnly() {
  rows.value = (await ratesAPI.models()).data
}

function openEdit(r: any) {
  editing.value = r
  form.value = {
    input_price: Number(r.input_price) || 0,
    output_price: Number(r.output_price) || 0,
  }
  showModal.value = true
}

async function saveRate() {
  if (!editing.value) return
  try {
    await ratesAPI.updateModel(editing.value.model, {
      input_price: form.value.input_price,
      output_price: form.value.output_price,
    })
    message.success('费率已更新')
    showModal.value = false
    await reloadOnly()
  } catch (e: any) {
    message.error('保存失败: ' + (e?.message || '未知错误'))
    console.error(e)
  }
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background">
    <TopBar :crumbs="[{ label: 'Pricing' }, { label: 'Rates', active: true }]">
      <template #actions>
        <NButton size="small" @click="load">刷新</NButton>
      </template>
    </TopBar>

    <div class="p-6 flex flex-col gap-5">
      <div>
        <h1 class="text-[20px] font-semibold text-text-primary">费率管理</h1>
        <p class="text-sm text-text-secondary mt-0.5">
          按模型配置输入/输出价格（单位：美元 / 1M tokens）。
          模型列表来自 Platforms 页面中各厂商配置的模型。同名模型只显示一行。
          是否收费由 Platforms 页面各厂商的 Paid/Free 标记决定。
        </p>
      </div>

      <!-- Loading spinner -->
      <NSpin v-if="loading" class="self-center py-16" size="large" />

      <div v-if="!loading" class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable
          :columns="columns"
          :data="rows"
          :bordered="false"
          :pagination="false"
          size="small"
        />
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <NModal
      v-model:show="showModal"
      preset="card"
      title="编辑费率"
      style="width: 480px"
    >
      <NForm label-placement="top">
        <div class="text-sm text-text-secondary mb-3">
          模型: <span class="font-mono font-semibold text-text-primary">{{ editing?.model }}</span>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <NFormItem label="输入价格 / 1M tokens">
            <NInputNumber v-model:value="form.input_price" :precision="4" :step="0.1" :min="0" class="w-full" />
          </NFormItem>
          <NFormItem label="输出价格 / 1M tokens">
            <NInputNumber v-model:value="form.output_price" :precision="4" :step="0.1" :min="0" class="w-full" />
          </NFormItem>
        </div>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-3">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" @click="saveRate">保存</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>
