<script setup lang="ts">
defineProps<{ crumbs: { label: string; active?: boolean }[] }>()
</script>
<template>
  <header class="topbar h-[68px] bg-surface border-b border-border sticky top-0 z-40 flex items-center justify-between px-8 backdrop-blur-md bg-surface/90">
    <div class="flex items-center gap-2 text-on-surface-variant">
      <span class="text-[13px] font-semibold text-text-primary tracking-tight">Relay Console</span>
      <template v-for="(crumb, i) in crumbs" :key="i"><span class="material-symbols-outlined text-[14px] text-text-secondary">chevron_right</span><span class="text-[13px]" :class="crumb.active ? 'text-text-primary font-medium' : 'text-text-secondary'">{{ crumb.label }}</span></template>
    </div>
    <div class="flex items-center gap-3"><slot name="actions" /><div class="h-8 pl-3 border-l border-border flex items-center gap-2 text-xs text-text-secondary"><span class="avatar">A</span>Admin</div></div>
  </header>
</template>
