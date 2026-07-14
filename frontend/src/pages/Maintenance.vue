<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { api } from '@/services/api'
import type { MaintenanceOrder } from '@/types/domain'

const orders = ref<MaintenanceOrder[]>([])

onMounted(async () => {
  orders.value = await api.maintenanceOrders()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="工单维修" description="统一管理租客报修、派单、维修进度与验收结果，保障居住体验和响应效率。" action-label="创建工单" :action-permission="pageActionPermissions.maintenanceCreate" />

    <div class="grid grid-cols-4 gap-5">
      <div class="panel p-5"><p class="eyebrow">未派单</p><p class="mt-3 text-3xl font-bold text-blue-700 tabular">12</p></div>
      <div class="panel p-5"><p class="eyebrow">处理中</p><p class="mt-3 text-3xl font-bold text-amber-700 tabular">18</p></div>
      <div class="panel p-5"><p class="eyebrow">待确认</p><p class="mt-3 text-3xl font-bold text-violet-700 tabular">6</p></div>
      <div class="panel p-5"><p class="eyebrow">今日完成</p><p class="mt-3 text-3xl font-bold text-emerald-700 tabular">23</p></div>
    </div>

    <DataTable :columns="['工单编号', '问题描述', '房间/租客', '分类', '优先级', '状态', '负责人', '截止时间']">
      <tr v-for="order in orders" :key="order.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3 font-semibold text-slate-950">{{ order.id }}</td>
        <td class="px-5 py-3"><p class="font-semibold">{{ order.title }}</p><p class="text-xs text-slate-500">创建 {{ order.created_at }}</p></td>
        <td class="px-5 py-3"><p class="font-semibold">{{ order.room }}</p><p class="text-xs text-slate-500">{{ order.tenant }}</p></td>
        <td class="px-5 py-3 text-slate-500">{{ order.category }}</td>
        <td class="px-5 py-3"><StatusChip :status="order.priority" /></td>
        <td class="px-5 py-3"><StatusChip :status="order.status" /></td>
        <td class="px-5 py-3 text-slate-500">{{ order.assignee }}</td>
        <td class="px-5 py-3 font-semibold text-slate-700">{{ order.due_at }}</td>
      </tr>
    </DataTable>
  </section>
</template>
