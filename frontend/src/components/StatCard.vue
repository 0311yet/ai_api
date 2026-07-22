<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  sub?: string
  accentColor?: string  // info | success | warning | purple | orange
  tag?: string
  tagType?: 'success' | 'info' | 'warning' | 'error'
}>()

const colorMap: Record<string, string> = {
  info: 'bg-info',
  success: 'bg-success',
  warning: 'bg-warning',
  purple: 'bg-[#a855f7]',
  orange: 'bg-[#f97316]',
}
</script>

<template>
  <div class="bg-surface-container border border-border rounded-xl p-5 relative overflow-hidden group">
    <!-- Accent bar -->
    <div
      v-if="accentColor"
      class="absolute left-0 top-0 bottom-0 w-1 rounded-l"
      :class="colorMap[accentColor]"
    ></div>
    <!-- Hover glow -->
    <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
      :class="accentColor ? `bg-gradient-to-br from-${accentColor}/5 to-transparent` : ''"
    ></div>
    <!-- Content -->
    <div class="relative">
      <div class="text-[12px] text-text-secondary uppercase tracking-wider mb-2">{{ label }}</div>
      <div class="flex items-baseline gap-2">
        <div class="text-[28px] font-bold text-text-primary leading-[34px] tracking-tight">{{ value }}</div>
        <div v-if="tag" class="text-[10px] px-1.5 py-0.5 rounded border" :class="{
          'text-success bg-success/10 border-success/20': tagType === 'success',
          'text-info bg-info/10 border-info/30': tagType === 'info',
          'text-warning bg-warning/10 border-warning/30': tagType === 'warning',
        }">{{ tag }}</div>
      </div>
      <div v-if="sub" class="text-[12px] text-text-secondary mt-1">{{ sub }}</div>
    </div>
  </div>
</template>