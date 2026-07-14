<script setup lang="ts">
import { computed } from 'vue'
import {
  Building2,
  ClipboardList,
  FileText,
  Gauge,
  Home,
  Landmark,
  ReceiptText,
  Search,
  Settings,
  UserRound,
  Users,
  Wrench,
} from '@lucide/vue'
import type { Component } from 'vue'
import { pageActionPermissions, pagePermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import type { PermissionKey, RoleKey } from '@/types/auth'
import type { PageKey } from '@/types/navigation'

const props = defineProps<{
  currentPage: PageKey
}>()

const emit = defineEmits<{
  change: [page: PageKey]
}>()

const { currentRole, currentUser, roles, hasPermission, setRole } = usePermissions()

const navItems: Array<{ key: PageKey; label: string; hint: string; icon: Component; permission: PermissionKey }> = [
  { key: 'dashboard', label: '管理控制台', hint: '运营驾驶舱', icon: Gauge, permission: pagePermissions.dashboard },
  { key: 'properties', label: '房源管理', hint: '楼栋与房间', icon: Building2, permission: pagePermissions.properties },
  { key: 'tenants', label: '租客列表', hint: '住户档案', icon: Users, permission: pagePermissions.tenants },
  { key: 'contracts', label: '合同管理', hint: '租约与签署', icon: FileText, permission: pagePermissions.contracts },
  { key: 'maintenance', label: '工单维修', hint: '报修处理', icon: Wrench, permission: pagePermissions.maintenance },
  { key: 'finance', label: '财务管理', hint: '账单与收支', icon: Landmark, permission: pagePermissions.finance },
  { key: 'reconciliation', label: '流水对账', hint: '银行流水', icon: ReceiptText, permission: pagePermissions.reconciliation },
]

const visibleNavItems = computed(() => navItems.filter((item) => hasPermission(item.permission)))
</script>

<template>
  <div class="min-h-screen bg-surface text-slate-900">
    <aside class="fixed inset-y-0 left-0 z-20 flex w-[260px] flex-col bg-brand-900 text-white shadow-2xl shadow-brand-950/20">
      <div class="flex h-20 items-center gap-3 px-6">
        <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
          <Home class="h-6 w-6 text-emerald-300" />
        </div>
        <div>
          <p class="text-lg font-bold tracking-tight">Propertied</p>
          <p class="text-xs font-medium text-slate-300">公寓运营系统</p>
        </div>
      </div>

      <div class="px-4 pb-3">
        <label class="block text-xs font-semibold text-slate-400">演示角色</label>
        <select
          class="mt-2 h-10 w-full rounded-lg border border-white/10 bg-white/10 px-3 text-sm font-semibold text-white outline-none focus:ring-4 focus:ring-emerald-400/20"
          :value="currentRole"
          @change="setRole(($event.target as HTMLSelectElement).value as RoleKey)"
        >
          <option v-for="role in roles" :key="role.key" class="text-slate-900" :value="role.key">
            {{ role.label }}
          </option>
        </select>
      </div>

      <nav class="mt-2 flex-1 space-y-1 px-3">
        <button
          v-for="item in visibleNavItems"
          :key="item.key"
          type="button"
          :class="[
            'group relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition',
            props.currentPage === item.key
              ? 'bg-white/10 text-white'
              : 'text-slate-300 hover:bg-white/5 hover:text-white',
          ]"
          @click="emit('change', item.key)"
        >
          <span v-if="props.currentPage === item.key" class="absolute left-0 h-8 w-1 rounded-r-full bg-emerald-400" />
          <component :is="item.icon" class="ml-1 h-5 w-5" />
          <span>
            <span class="block text-sm font-semibold">{{ item.label }}</span>
            <span class="block text-xs text-slate-400 group-hover:text-slate-300">{{ item.hint }}</span>
          </span>
        </button>
      </nav>

      <div class="m-4 rounded-2xl border border-white/10 bg-white/5 p-4">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-200">
            <UserRound class="h-5 w-5" />
          </div>
          <div>
            <p class="text-sm font-semibold">{{ currentUser?.name ?? '运营中心' }}</p>
            <p class="text-xs text-slate-400">{{ currentUser?.role_label ?? '加载权限中' }} · 上海</p>
          </div>
        </div>
      </div>
    </aside>

    <div class="pl-[260px]">
      <header class="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-slate-200/80 bg-surface/90 px-8 backdrop-blur">
        <div class="relative">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input class="h-11 w-[420px] rounded-xl border border-slate-200 bg-white pl-10 pr-4 text-sm outline-none transition placeholder:text-slate-400 focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="搜索房间、租客、合同、工单" />
        </div>
        <div class="flex items-center gap-3">
          <button v-if="hasPermission(pageActionPermissions.tasksView)" class="secondary-button" type="button">
            <ClipboardList class="h-4 w-4" />今日待办 36
          </button>
          <button v-if="hasPermission(pageActionPermissions.systemSettings)" class="rounded-xl p-2.5 text-slate-500 transition hover:bg-white hover:text-brand-900" type="button">
            <Settings class="h-5 w-5" />
          </button>
        </div>
      </header>

      <main class="p-8">
        <slot />
      </main>
    </div>
  </div>
</template>
