<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
}>()

const statusMap: Record<string, { label: string; className: string }> = {
  occupied: { label: '已出租', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  vacant: { label: '空置', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
  reserved: { label: '已预定', className: 'bg-blue-50 text-blue-700 ring-blue-200' },
  maintenance: { label: '维修中', className: 'bg-amber-50 text-amber-700 ring-amber-200' },
  active: { label: '生效中', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  expiring: { label: '即将到期', className: 'bg-amber-50 text-amber-700 ring-amber-200' },
  pending: { label: '待处理', className: 'bg-amber-50 text-amber-700 ring-amber-200' },
  terminated: { label: '已终止', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
  paid: { label: '已支付', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  overdue: { label: '已逾期', className: 'bg-rose-50 text-rose-700 ring-rose-200' },
  reconciled: { label: '已对账', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  matched: { label: '已匹配', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  exception: { label: '异常', className: 'bg-rose-50 text-rose-700 ring-rose-200' },
  open: { label: '待派单', className: 'bg-blue-50 text-blue-700 ring-blue-200' },
  in_progress: { label: '处理中', className: 'bg-amber-50 text-amber-700 ring-amber-200' },
  waiting: { label: '待确认', className: 'bg-violet-50 text-violet-700 ring-violet-200' },
  resolved: { label: '已完成', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  low: { label: '低', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
  medium: { label: '中', className: 'bg-blue-50 text-blue-700 ring-blue-200' },
  high: { label: '高', className: 'bg-amber-50 text-amber-700 ring-amber-200' },
  urgent: { label: '紧急', className: 'bg-rose-50 text-rose-700 ring-rose-200' },
}

const chip = computed(() => statusMap[props.status] ?? { label: props.status, className: 'bg-slate-100 text-slate-600 ring-slate-200' })
</script>

<template>
  <span :class="['inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', chip.className]">
    {{ chip.label }}
  </span>
</template>
