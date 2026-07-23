<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NDataTable, NButton, NModal, NForm, NFormItem, NInputNumber, NTag,
  useMessage,
} from 'naive-ui'
import TopBar from '../components/TopBar.vue'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const rows = ref<any[]>([])

// providers 用 is_paid 标记 → 在该 provider 下的 PoolItem 计费时
// True → 按 paid 价；False → 按 free 价
// 这里单独维护 provider 列表，方便弹窗里切换 is_paid
const providers = ref<any[]>([])

const showModal = ref(false)
const editing = ref<any>(null)  // 当前编辑的 PoolItem
const form = ref({
  free_input_price: 0,
  free_output_price: 0,
  paid_input_price: 0,
  paid_output_price: 0,
})

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: 'Pool', key: 'pool_id', width: 80 },
  {
    title: 'Provider', key: 'provider_name',
    render: (r: any) => h('span', { class: 'font-semibold text-sm text-text-primary' }, r.provider_name || '—'),
  },
  {
    title: 'Model', key: 'model',
    render: (r: any) => h('span', { class: 'font-mono text-[12px] text-text-secondary' }, r.model),
  },
  {
    title: 'Provider Type',
    key: 'is_paid',
    width: 130,
    // 直接渲染 provider.is_paid - 需要查 provider 状态
    // 我们在 load 时把 provider 的 is_paid 注入到行数据
    render: (r: any) => h(NTag,
      r.provider_is_paid
        ? { type: 'warning', size: 'small', round: true }
        : { type: 'success', size: 'small', round: true },
      { default: () => r.provider_is_paid ? '付费 API' : '免费 API' }
    ),
  },
  { title: 'Free 输入价', key: 'free_input_price', width: 130,
    render: (r: any) => fmtPrice(r.free_input_price) },
  { title: 'Free 输出价', key: 'free_output_price', width: 130,
    render: (r: any) => fmtPrice(r.free_output_price) },
  { title: 'Paid 输入价', key: 'paid_input_price', width: 130,
    render: (r: any) => fmtPrice(r.paid_input_price) },
  { title: 'Paid 输出价', key: 'paid_output_price', width: 130,
    render: (r: any) => fmtPrice(r.paid_output_price) },
  {
    title: 'Actions', key: 'actions', width: 140,
    render: (r: any) => [
      h(NButton, { size: 'tiny', onClick: () => openEdit(r) }, { default: () => '编辑费率' }),
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
    const [rateRes, provRes] = await Promise.all([
      api.get('/admin/rates'),
      api.get('/admin/providers'),
    ])
    providers.value = provRes.data || []
    const provMap = new Map<number, any>()
    for (const p of providers.value) provMap.set(p.id, p)

    rows.value = (rateRes.data || []).map((row: any) => {
      const prov = provMap.get(row.provider_id)
      return { ...row, provider_is_paid: prov?.is_paid ?? false }
    })
  } catch (e: any) {
    message.error('加载失败: ' + (e?.message || '未知错误'))
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function reloadRatesOnly() {
  const rateRes = await api.get('/admin/rates')
  const provMap = new Map<number, any>()
  for (const p of providers.value) provMap.set(p.id, p)
  rows.value = (rateRes.data || []).map((row: any) => {
    const prov = provMap.get(row.provider_id)
    return { ...row, provider_is_paid: prov?.is_paid ?? false }
  })
}

function openEdit(r: any) {
  editing.value = r
  form.value = {
    free_input_price: Number(r.free_input_price) || 0,
    free_output_price: Number(r.free_output_price) || 0,
    paid_input_price: Number(r.paid_input_price) || 0,
    paid_output_price: Number(r.paid_output_price) || 0,
  }
  showModal.value = true
}

async function saveRate() {
  if (!editing.value) return
  try {
    const payload = {
      free_input_price: form.value.free_input_price,
      free_output_price: form.value.free_output_price,
      paid_input_price: form.value.paid_input_price,
      paid_output_price: form.value.paid_output_price,
    }
    await api.put(`/admin/rates/${editing.value.id}`, payload)
    message.success('费率已更新')
    showModal.value = false
    await reloadRatesOnly()
  } catch (e: any) {
    message.error('保存失败: ' + (e?.message || '未知错误'))
    console.error(e)
  }
}

async function toggleProviderPaid(item: any) {
  if (!item.provider_id) return
  const newPaid = !item.provider_is_paid
  try {
    await api.put(`/admin/rates/provider/${item.provider_id}?is_paid=${newPaid}`)
    message.success(`已切换为${newPaid ? '付费' : '免费'} API`)
    // 同步所有该 provider 下的条目
    for (const r of rows.value) {
      if (r.provider_id === item.provider_id) r.provider_is_paid = newPaid
    }
    for (const p of providers.value) {
      if (p.id === item.provider_id) p.is_paid = newPaid
    }
  } catch (e: any) {
    message.error('切换失败: ' + (e?.message || '未知错误'))
    console.error(e)
  }
}

// 额外列：provider 类型切换按钮（独立按钮 + 单 provider 一次性 toggle）
const extraColumns = [
  {
    title: '切换计费类型',
    key: 'switch_paid',
    width: 140,
    render: (r: any) =>
      h(
        NButton,
        { size: 'tiny', onClick: () => toggleProviderPaid(r) },
        { default: () => r.provider_is_paid ? '标记为免费' : '标记为付费' }
      ),
  },
]

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
          为每个 Pool × Provider × Model 配置免费/付费 API 的输入输出价格（单位：美元 / 1M tokens）。
          Provider 的计费类型决定具体调用时用哪一套价格。
        </p>
      </div>

      <div class="bg-surface-container border border-border rounded-xl overflow-hidden">
        <NDataTable
          :columns="[...columns, ...extraColumns]"
          :data="rows"
          :loading="loading"
          :bordered="false"
          :pagination="false"
          size="small"
        />
      </div>

      <div class="text-[12px] text-text-secondary">
        说明：Provider 类型 =「免费 API」时按 Free 价格计算；「付费 API」时按 Paid 价格计算。
        切换 Provider 类型会同步影响该 Provider 下所有 PoolItem。
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <NModal
      v-model:show="showModal"
      preset="card"
      title="编辑费率"
      style="width: 520px"
    >
      <NForm label-placement="top">
        <div class="text-sm text-text-secondary mb-3">
          <div provider_name><span class="font-semibold text-text-primary">{{ editing?.provider_name }}</span> • {{ editing?.model }}</div>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <NFormItem label="Free 输入价 / 1M tokens">
            <NInputNumber v-model:value="form.free_input_price" :precision="4" :step="0.1" :min="0" class="w-full" />
          </NFormItem>
          <NFormItem label="Free 输出价 / 1M tokens">
            <NInputNumber v-model:value="form.free_output_price" :precision="4" :step="0.1" :min="0" class="w-full" />
          </NFormItem>
          <NFormItem label="Paid 输入价 / 1M tokens">
            <NInputNumber v-model:value="form.paid_input_price" :precision="4" :step="0.1" :min="0" class="w-full" />
          </NFormItem>
          <NFormItem label="Paid 输出价 / 1M tokens">
            <NInputNumber v-model:value="form.paid_output_price" :precision="4" :step="0.1" :min="0" class="w-full" />
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
