<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Activity, AlertTriangle, Banknote, Building2 } from '@lucide/vue'
import StatCard from '@/components/ui/StatCard.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { api, compactCurrency, currency } from '@/services/api'
import type { DashboardSummary } from '@/types/domain'

const summary = ref<DashboardSummary | null>(null)
const loading = ref(true)
const error = ref('')
const icons = [Building2, Activity, Banknote, AlertTriangle]
const { hasPermission } = usePermissions()

onMounted(async () => {
  try {
    summary.value = await api.dashboard()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载数据失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-end justify-between">
      <div>
        <p class="eyebrow">Operation Cockpit</p>
        <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">管理控制台</h1>
        <p class="mt-2 text-sm text-slate-500">实时掌握房源出租、租金收缴、合同风险与维修工单状态。</p>
      </div>
      <button v-if="hasPermission(pageActionPermissions.dashboardExport)" class="primary-button" type="button">生成运营日报</button>
    </div>

    <div v-if="loading" class="panel p-8 text-sm text-slate-500">正在加载运营数据...</div>
    <div v-else-if="error" class="panel border-rose-200 bg-rose-50 p-8 text-sm text-rose-700">{{ error }}</div>

    <template v-else-if="summary">
      <div class="grid grid-cols-4 gap-5">
        <StatCard v-for="(metric, index) in summary.metrics" :key="metric.label" v-bind="metric" :icon="icons[index]" />
      </div>

      <div class="grid grid-cols-[1.2fr_0.8fr] gap-5">
        <article class="panel p-6">
          <div class="flex items-center justify-between">
            <div>
              <p class="eyebrow">Income Trend</p>
              <h2 class="section-title mt-2">月度收入趋势</h2>
            </div>
            <p class="text-2xl font-bold text-slate-950 tabular">{{ compactCurrency(summary.monthly_income) }}</p>
          </div>
          <div class="mt-8 flex h-64 items-end gap-4 border-b border-slate-200 px-2 pb-3">
            <div v-for="item in summary.income_trend" :key="item.month" class="flex flex-1 flex-col items-center gap-3">
              <div class="w-full rounded-t-xl bg-brand-900 shadow-card" :style="{ height: `${Math.max(24, item.income / 5200)}px` }" />
              <span class="text-xs font-semibold text-slate-500">{{ item.month }}</span>
            </div>
          </div>
        </article>

        <article class="panel p-6">
          <p class="eyebrow">Occupancy</p>
          <h2 class="section-title mt-2">出租率健康度</h2>
          <div class="mt-7 flex items-center gap-6">
            <div class="grid h-36 w-36 place-items-center rounded-full p-3" :style="{ background: `conic-gradient(#10b981 ${summary.occupancy_rate * 3.6}deg, #e2e8f0 0deg)` }">
              <div class="grid h-full w-full place-items-center rounded-full bg-white">
                <span class="text-3xl font-bold text-slate-950 tabular">{{ summary.occupancy_rate }}%</span>
              </div>
            </div>
            <div class="space-y-4 text-sm">
              <p class="text-slate-500">出租率保持在安全区间，空置房源需优先安排带看与渠道推广。</p>
              <div class="grid grid-cols-2 gap-3">
                <div class="rounded-xl bg-slate-50 p-3"><p class="text-slate-500">待办</p><p class="text-xl font-bold tabular">{{ summary.pending_tasks }}</p></div>
                <div class="rounded-xl bg-amber-50 p-3"><p class="text-amber-700">到期</p><p class="text-xl font-bold tabular">{{ summary.expiring_contracts }}</p></div>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div class="grid grid-cols-2 gap-5">
        <article class="panel p-6">
          <h2 class="section-title">近期合同</h2>
          <div class="mt-4 divide-y divide-slate-100">
            <div v-for="contract in summary.recent_contracts" :key="contract.id" class="flex items-center justify-between py-4">
              <div>
                <p class="font-semibold text-slate-900">{{ contract.tenant }} · {{ contract.room }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ contract.id }} · 到期 {{ contract.end_date }}</p>
              </div>
              <div class="text-right">
                <p class="font-semibold tabular">{{ currency(contract.monthly_rent) }}</p>
                <StatusChip :status="contract.status" />
              </div>
            </div>
          </div>
        </article>

        <article class="panel p-6">
          <h2 class="section-title">紧急工单</h2>
          <div class="mt-4 divide-y divide-slate-100">
            <div v-for="order in summary.urgent_work_orders" :key="order.id" class="flex items-center justify-between py-4">
              <div>
                <p class="font-semibold text-slate-900">{{ order.title }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ order.room }} · {{ order.assignee }} · {{ order.due_at }}</p>
              </div>
              <div class="flex flex-col items-end gap-2">
                <StatusChip :status="order.priority" />
                <StatusChip :status="order.status" />
              </div>
            </div>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>
