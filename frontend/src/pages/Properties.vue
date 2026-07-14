<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/ui/DataTable.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { api, currency } from '@/services/api'
import type { Property } from '@/types/domain'

const properties = ref<Property[]>([])

onMounted(async () => {
  properties.value = await api.properties()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar title="房源管理" description="集中管理楼栋、房间、租金、出租状态与房源标签，支持运营人员快速判断可租资源。" action-label="新增房源" :action-permission="pageActionPermissions.propertyCreate" />

    <div class="grid grid-cols-4 gap-5">
      <div class="panel p-5"><p class="eyebrow">总房源</p><p class="mt-3 text-3xl font-bold tabular">248</p></div>
      <div class="panel p-5"><p class="eyebrow">已出租</p><p class="mt-3 text-3xl font-bold text-emerald-600 tabular">230</p></div>
      <div class="panel p-5"><p class="eyebrow">空置</p><p class="mt-3 text-3xl font-bold text-amber-600 tabular">14</p></div>
      <div class="panel p-5"><p class="eyebrow">维修中</p><p class="mt-3 text-3xl font-bold text-rose-600 tabular">4</p></div>
    </div>

    <DataTable :columns="['房源编号', '楼栋/房号', '户型面积', '月租金', '当前租客', '状态', '标签']">
      <tr v-for="item in properties" :key="item.id" class="h-[52px] transition hover:bg-slate-50/80">
        <td class="px-5 py-3 font-semibold text-slate-950">{{ item.id }}</td>
        <td class="px-5 py-3"><span class="font-semibold">{{ item.building }}-{{ item.room }}</span></td>
        <td class="px-5 py-3 text-slate-500">{{ item.layout }} · {{ item.area }}㎡</td>
        <td class="px-5 py-3 font-semibold tabular">{{ currency(item.rent) }}</td>
        <td class="px-5 py-3 text-slate-500">{{ item.tenant ?? '待出租' }}</td>
        <td class="px-5 py-3"><StatusChip :status="item.status" /></td>
        <td class="px-5 py-3">
          <div class="flex flex-wrap gap-1.5">
            <span v-for="tag in item.tags" :key="tag" class="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{{ tag }}</span>
          </div>
        </td>
      </tr>
    </DataTable>
  </section>
</template>
