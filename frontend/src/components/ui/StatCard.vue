<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(
  defineProps<{
    label: string
    value: string
    change: string
    tone?: 'primary' | 'success' | 'warning' | 'danger'
    icon?: Component
  }>(),
  { tone: 'primary' },
)

const toneClass = {
  primary: 'bg-slate-100 text-brand-900',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  danger: 'bg-rose-50 text-rose-700',
}
</script>

<template>
  <article class="panel p-5">
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="eyebrow">{{ label }}</p>
        <p class="mt-3 text-3xl font-bold tracking-[-0.03em] text-slate-950 tabular">{{ value }}</p>
        <p class="mt-2 text-sm font-medium text-slate-500">{{ change }}</p>
      </div>
      <div v-if="icon" :class="['rounded-xl p-3', toneClass[tone]]">
        <component :is="icon" class="h-5 w-5" />
      </div>
    </div>
  </article>
</template>
