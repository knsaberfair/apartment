<script setup lang="ts">
import { Filter, Plus, Search } from '@lucide/vue'
import { usePermissions } from '@/composables/usePermissions'
import type { PermissionKey } from '@/types/auth'

const emit = defineEmits<{
  action: []
  filter: []
  'update:modelValue': [value: string]
}>()

withDefaults(
  defineProps<{
    title: string
    description: string
    modelValue?: string
    actionLabel?: string
    searchPlaceholder?: string
    actionPermission?: PermissionKey
    filterPermission?: PermissionKey
  }>(),
  {
    actionLabel: '新增记录',
    searchPlaceholder: '搜索房源、租客或编号',
  },
)

const { hasPermission } = usePermissions()
</script>

<template>
  <div class="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
    <div>
      <p class="eyebrow">Apartment Operations</p>
      <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">{{ title }}</h1>
      <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{{ description }}</p>
    </div>
    <div class="flex w-full flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center xl:w-auto xl:justify-end">
      <label class="relative w-full sm:w-72">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input class="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" aria-label="页面搜索" :placeholder="searchPlaceholder" :value="modelValue" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
      </label>
      <button v-if="filterPermission && hasPermission(filterPermission)" class="secondary-button w-full sm:w-auto" type="button" @click="emit('filter')">
        <Filter class="h-4 w-4" />筛选
      </button>
      <button v-if="actionPermission && hasPermission(actionPermission)" class="primary-button w-full sm:w-auto" type="button" @click="emit('action')">
        <Plus class="h-4 w-4" />{{ actionLabel }}
      </button>
    </div>
  </div>
</template>
