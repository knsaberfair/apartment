<script setup lang="ts">
import { computed } from 'vue'
import { statusLabel } from '@/config/statusLabels'

const props = defineProps<{
  status: string
}>()

const statusClassMap: Record<string, string> = {
  occupied: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  vacant: 'bg-slate-100 text-slate-600 ring-slate-200',
  reserved: 'bg-blue-50 text-blue-700 ring-blue-200',
  maintenance: 'bg-amber-50 text-amber-700 ring-amber-200',
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  expiring: 'bg-amber-50 text-amber-700 ring-amber-200',
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  terminated: 'bg-slate-100 text-slate-600 ring-slate-200',
  paid: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  overdue: 'bg-rose-50 text-rose-700 ring-rose-200',
  reconciled: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  matched: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  exception: 'bg-rose-50 text-rose-700 ring-rose-200',
  open: 'bg-blue-50 text-blue-700 ring-blue-200',
  in_progress: 'bg-amber-50 text-amber-700 ring-amber-200',
  waiting: 'bg-violet-50 text-violet-700 ring-violet-200',
  resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
  medium: 'bg-blue-50 text-blue-700 ring-blue-200',
  high: 'bg-amber-50 text-amber-700 ring-amber-200',
  urgent: 'bg-rose-50 text-rose-700 ring-rose-200',
}

const chip = computed(() => ({
  label: statusLabel(props.status),
  className: statusClassMap[props.status] ?? 'bg-slate-100 text-slate-600 ring-slate-200',
}))
</script>

<template>
  <span :class="['inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', chip.className]">
    {{ chip.label }}
  </span>
</template>
