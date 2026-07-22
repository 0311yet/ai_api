<script setup lang="ts">
defineProps<{ crumbs: { label: string; active?: boolean }[] }>()
</script>

<template>
  <header class="h-16 bg-surface border-b border-border sticky top-0 z-40 flex items-center justify-between px-6 transition-colors duration-200 backdrop-blur-md bg-surface/90">
    <!-- Breadcrumbs -->
    <div class="flex items-center gap-2 text-on-surface-variant">
      <span class="text-sm font-semibold text-text-primary tracking-tight">AI Gateway</span>
      <template v-for="(crumb, i) in crumbs" :key="i">
        <span class="material-symbols-outlined text-[14px] text-text-secondary">chevron_right</span>
        <span class="text-sm" :class="crumb.active ? 'text-primary' : 'text-text-secondary'">{{ crumb.label }}</span>
      </template>
    </div>
    <!-- Right actions -->
    <div class="flex items-center gap-3">
      <slot name="actions" />
      <button class="w-9 h-9 flex items-center justify-center rounded-full text-on-surface-variant hover:text-primary hover:bg-surface-container-highest transition-colors">
        <span class="material-symbols-outlined text-[20px]">account_circle</span>
      </button>
    </div>
  </header>
</template>