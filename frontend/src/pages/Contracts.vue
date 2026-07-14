<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { api, currency } from '@/services/api'
import type { Contract } from '@/types/domain'

const contracts = ref<Contract[]>([])

onMounted(async () => {
  contracts.value = await api.contracts()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="合同管理中心" description="跟踪合同签署、生效、到期与终止状态，提前识别租约风险并推动续签。" action-label="新建合同" :action-permission="pageActionPermissions.contractCreate" />

    <div class="grid grid-cols-[0.75fr_1.25fr] gap-5">
      <article class="panel p-6">
        <p class="eyebrow">Lease Risk</p>
        <h2 class="section-title mt-2">到期提醒</h2>
        <div class="mt-5 space-y-4">
          <div class="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-100">
            <p class="text-sm font-semibold text-amber-800">30 天内到期</p>
            <p class="mt-2 text-3xl font-bold text-amber-700 tabular">8</p>
          </div>
          <div class="rounded-2xl bg-rose-50 p-4 ring-1 ring-rose-100">
            <p class="text-sm font-semibold text-rose-800">待签署合同</p>
            <p class="mt-2 text-3xl font-bold text-rose-700 tabular">4</p>
          </div>
        </div>
      </article>

      <article class="panel p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="eyebrow">Contract Pipeline</p>
            <h2 class="section-title mt-2">合同流程</h2>
          </div>
          <span class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">SLA 96%</span>
        </div>
        <div class="mt-8 grid grid-cols-4 gap-3">
          <div v-for="step in ['草拟', '待签署', '已生效', '归档']" :key="step" class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="text-sm font-semibold text-slate-600">{{ step }}</p>
            <div class="mt-4 h-2 rounded-full bg-slate-200">
              <div class="h-2 rounded-full bg-brand-900" :style="{ width: step === '已生效' ? '88%' : step === '待签署' ? '42%' : '64%' }" />
            </div>
          </div>
        </div>
      </article>
    </div>

    <DataTable :columns="['合同编号', '租客/房间', '租期', '月租金', '押金', '剩余天数', '状态']">
      <tr v-for="contract in contracts" :key="contract.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3 font-semibold text-slate-950">{{ contract.id }}</td>
        <td class="px-5 py-3"><p class="font-semibold">{{ contract.tenant }}</p><p class="text-xs text-slate-500">{{ contract.room }}</p></td>
        <td class="px-5 py-3 text-slate-500">{{ contract.start_date }} 至 {{ contract.end_date }}</td>
        <td class="px-5 py-3 font-semibold tabular">{{ currency(contract.monthly_rent) }}</td>
        <td class="px-5 py-3 text-slate-500 tabular">{{ currency(contract.deposit) }}</td>
        <td class="px-5 py-3 font-semibold tabular" :class="contract.days_left < 60 ? 'text-amber-700' : 'text-slate-700'">{{ contract.days_left }} 天</td>
        <td class="px-5 py-3"><StatusChip :status="contract.status" /></td>
      </tr>
    </DataTable>
  </section>
</template>
