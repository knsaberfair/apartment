<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { api, currency } from '@/services/api'
import type { Tenant } from '@/types/domain'

const tenants = ref<Tenant[]>([])

onMounted(async () => {
  tenants.value = await api.tenants()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="租客列表" description="维护租客联系方式、入住时间、关联合同和应收余额，减少人工查询成本。" action-label="新增租客" :action-permission="pageActionPermissions.tenantCreate" />

    <DataTable :columns="['租客', '联系方式', '房间', '合同编号', '入住/到期', '付款状态', '当前余额']">
      <tr v-for="tenant in tenants" :key="tenant.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3"><p class="font-semibold text-slate-950">{{ tenant.name }}</p><p class="text-xs text-slate-500">{{ tenant.id }}</p></td>
        <td class="px-5 py-3 text-slate-500">{{ tenant.phone }}</td>
        <td class="px-5 py-3 font-semibold">{{ tenant.room }}</td>
        <td class="px-5 py-3 text-slate-500">{{ tenant.contract_id }}</td>
        <td class="px-5 py-3 text-slate-500">{{ tenant.move_in_date }} / {{ tenant.lease_end }}</td>
        <td class="px-5 py-3"><StatusChip :status="tenant.payment_status" /></td>
        <td class="px-5 py-3 font-semibold tabular" :class="tenant.balance > 0 ? 'text-amber-700' : 'text-emerald-700'">{{ currency(tenant.balance) }}</td>
      </tr>
    </DataTable>
  </section>
</template>
