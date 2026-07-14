<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { api, currency } from '@/services/api'
import type { ReconciliationRecord } from '@/types/domain'

const records = ref<ReconciliationRecord[]>([])
const { hasPermission } = usePermissions()

onMounted(async () => {
  records.value = await api.reconciliation()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="财务流水对账单" description="核对银行流水、第三方支付与系统账单差异，定位异常款项并沉淀审计记录。" action-label="导入流水" :action-permission="pageActionPermissions.reconciliationImport" />

    <div class="panel p-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="eyebrow">Reconciliation Summary</p>
          <h2 class="section-title mt-2">今日对账概览</h2>
        </div>
        <button v-if="hasPermission(pageActionPermissions.reconciliationExport)" class="secondary-button" type="button">下载对账单</button>
      </div>
      <div class="mt-6 grid grid-cols-4 gap-4">
        <div class="rounded-2xl bg-slate-50 p-4"><p class="text-sm text-slate-500">总流水</p><p class="mt-2 text-2xl font-bold tabular">128</p></div>
        <div class="rounded-2xl bg-emerald-50 p-4"><p class="text-sm text-emerald-700">已匹配</p><p class="mt-2 text-2xl font-bold text-emerald-700 tabular">116</p></div>
        <div class="rounded-2xl bg-amber-50 p-4"><p class="text-sm text-amber-700">待确认</p><p class="mt-2 text-2xl font-bold text-amber-700 tabular">9</p></div>
        <div class="rounded-2xl bg-rose-50 p-4"><p class="text-sm text-rose-700">异常差额</p><p class="mt-2 text-2xl font-bold text-rose-700 tabular">3</p></div>
      </div>
    </div>

    <DataTable :columns="['对账编号', '日期', '银行流水', '系统流水', '付款方', '金额', '渠道', '差额', '状态']">
      <tr v-for="record in records" :key="record.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3 font-semibold text-slate-950">{{ record.id }}</td>
        <td class="px-5 py-3 text-slate-500">{{ record.date }}</td>
        <td class="px-5 py-3 text-slate-500">{{ record.bank_flow_id }}</td>
        <td class="px-5 py-3 text-slate-500">{{ record.system_flow_id }}</td>
        <td class="px-5 py-3 font-semibold">{{ record.payer }}</td>
        <td class="px-5 py-3 font-semibold tabular">{{ currency(record.amount) }}</td>
        <td class="px-5 py-3 text-slate-500">{{ record.channel }}</td>
        <td class="px-5 py-3 font-semibold tabular" :class="record.difference === 0 ? 'text-emerald-700' : 'text-rose-700'">{{ currency(record.difference) }}</td>
        <td class="px-5 py-3"><StatusChip :status="record.status" /></td>
      </tr>
    </DataTable>
  </section>
</template>
