<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { api, currency } from '@/services/api'
import type { FinanceTransaction } from '@/types/domain'

const transactions = ref<FinanceTransaction[]>([])

const income = computed(() => transactions.value.filter((item) => item.amount > 0).reduce((sum, item) => sum + item.amount, 0))
const expense = computed(() => Math.abs(transactions.value.filter((item) => item.amount < 0).reduce((sum, item) => sum + item.amount, 0)))
const pending = computed(() => transactions.value.filter((item) => item.status === 'pending' || item.status === 'overdue').reduce((sum, item) => sum + Math.max(item.amount, 0), 0))

onMounted(async () => {
  transactions.value = await api.transactions()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="财务管理" description="汇总租金、押金、维修支出与待收账款，帮助财务人员快速完成月度运营核算。" action-label="新增账单" :action-permission="pageActionPermissions.financeCreate" />

    <div class="grid grid-cols-3 gap-5">
      <div class="panel p-6"><p class="eyebrow">本页收入</p><p class="mt-3 text-3xl font-bold text-emerald-700 tabular">{{ currency(income) }}</p><p class="mt-2 text-sm text-slate-500">含租金与押金收入</p></div>
      <div class="panel p-6"><p class="eyebrow">本页支出</p><p class="mt-3 text-3xl font-bold text-rose-700 tabular">{{ currency(expense) }}</p><p class="mt-2 text-sm text-slate-500">维修与运营支出</p></div>
      <div class="panel p-6"><p class="eyebrow">待确认/逾期</p><p class="mt-3 text-3xl font-bold text-amber-700 tabular">{{ currency(pending) }}</p><p class="mt-2 text-sm text-slate-500">需跟进到账状态</p></div>
    </div>

    <DataTable :columns="['流水编号', '日期', '类型', '房间/租客', '金额', '支付方式', '状态', '备注']">
      <tr v-for="item in transactions" :key="item.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3 font-semibold text-slate-950">{{ item.id }}</td>
        <td class="px-5 py-3 text-slate-500">{{ item.date }}</td>
        <td class="px-5 py-3 font-semibold">{{ item.type }}</td>
        <td class="px-5 py-3"><p class="font-semibold">{{ item.room }}</p><p class="text-xs text-slate-500">{{ item.tenant }}</p></td>
        <td class="px-5 py-3 font-bold tabular" :class="item.amount >= 0 ? 'text-emerald-700' : 'text-rose-700'">{{ currency(item.amount) }}</td>
        <td class="px-5 py-3 text-slate-500">{{ item.method }}</td>
        <td class="px-5 py-3"><StatusChip :status="item.status" /></td>
        <td class="px-5 py-3 text-slate-500">{{ item.note }}</td>
      </tr>
    </DataTable>
  </section>
</template>
