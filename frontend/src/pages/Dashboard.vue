<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, AlertTriangle, Banknote, Building2 } from '@lucide/vue'
import { ElButton, ElCard } from 'element-plus'
import StatCard from '@/components/ui/StatCard.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { api, compactCurrency, currency, downloadBlob } from '@/services/api'
import type { DashboardSummary } from '@/types/domain'

const summary = ref<DashboardSummary | null>(null)
const loading = ref(true)
const exporting = ref(false)
const error = ref('')
const actionError = ref('')
const icons = [Building2, Activity, Banknote, AlertTriangle]
const { hasPermission } = usePermissions()
const trendMaxIncome = computed(() => Math.max(...(summary.value?.income_trend.map((item) => item.income) ?? [0]), 0))

function trendBarHeight(income: number) {
  if (trendMaxIncome.value <= 0) return 24
  return Math.max(24, Math.round((income / trendMaxIncome.value) * 220))
}

onMounted(async () => {
  try {
    summary.value = await api.dashboard()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载数据失败'
  } finally {
    loading.value = false
  }
})

async function exportDashboard() {
  if (!hasPermission(pageActionPermissions.dashboardExport)) return
  exporting.value = true
  actionError.value = ''
  try {
    downloadBlob(await api.exportDashboard(), 'dashboard-summary.csv')
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : '导出运营日报失败'
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="eyebrow">Operation Cockpit</p>
        <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">管理控制台</h1>
        <p class="mt-2 text-sm text-slate-500">实时掌握房源出租、租金收缴、合同风险与维修工单状态。</p>
      </div>
      <el-button v-if="hasPermission(pageActionPermissions.dashboardExport)" type="primary" :loading="exporting" @click="exportDashboard">生成运营日报</el-button>
    </div>

    <el-card v-if="actionError" shadow="never" class="rounded-2xl border-rose-200 bg-rose-50 text-sm text-rose-700">{{ actionError }}</el-card>
    <el-card v-if="loading" shadow="never" class="rounded-2xl text-sm text-slate-500">正在加载运营数据...</el-card>
    <el-card v-else-if="error" shadow="never" class="rounded-2xl border-rose-200 bg-rose-50 text-sm text-rose-700">{{ error }}</el-card>

    <template v-else-if="summary">
      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard v-for="(metric, index) in summary.metrics" :key="metric.label" v-bind="metric" :icon="icons[index]" />
      </div>

      <div class="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <el-card shadow="never" class="rounded-2xl">
          <div class="flex items-center justify-between">
            <div>
              <p class="eyebrow">Income Trend</p>
              <h2 class="section-title mt-2">月度收入趋势</h2>
            </div>
            <p class="text-2xl font-bold text-slate-950 tabular">{{ compactCurrency(summary.monthly_income) }}</p>
          </div>
          <div class="mt-8 flex h-64 items-end gap-4 border-b border-slate-200 px-2 pb-3">
            <div v-for="item in summary.income_trend" :key="item.month" class="flex flex-1 flex-col items-center gap-3">
              <div class="w-full rounded-t-xl bg-brand-900 shadow-card" :style="{ height: `${trendBarHeight(item.income)}px` }" />
              <span class="text-xs font-semibold text-slate-500">{{ item.month }}</span>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="rounded-2xl">
          <p class="eyebrow">Occupancy</p>
          <h2 class="section-title mt-2">出租率健康度</h2>
          <div class="mt-7 flex flex-col items-center gap-6 sm:flex-row">
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
        </el-card>
      </div>

      <div class="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <el-card shadow="never" class="rounded-2xl">
          <h2 class="section-title">近期合同</h2>
          <div class="mt-4 divide-y divide-slate-100">
            <div v-for="contract in summary.recent_contracts" :key="contract.id" class="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
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
        </el-card>

        <el-card shadow="never" class="rounded-2xl">
          <h2 class="section-title">紧急工单</h2>
          <div class="mt-4 divide-y divide-slate-100">
            <div v-for="order in summary.urgent_work_orders" :key="order.id" class="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
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
        </el-card>
      </div>
    </template>
  </section>
</template>
