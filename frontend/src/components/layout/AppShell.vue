<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Building2,
  ClipboardList,
  FileText,
  Gauge,
  Home,
  Landmark,
  ListChecks,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  PanelTop,
  ReceiptText,
  Settings,
  ShieldCheck,
  UserRound,
  Users,
  Wrench,
} from '@lucide/vue'
import type { Component } from 'vue'
import { ElDrawer } from 'element-plus'
import { pagePermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { api } from '@/services/api'
import type { PermissionKey, RoleKey } from '@/types/auth'
import type { BuiltInPageKey, PageKey } from '@/types/navigation'

const props = defineProps<{
  currentPage: PageKey
}>()

const emit = defineEmits<{
  change: [page: PageKey]
}>()

const { currentRole, currentUser, demoAccountsEnabled, demoRoles, menuResources, hasPermission, setRole, logout } = usePermissions()
const mobileMenuOpen = ref(false)
const sidebarCollapsed = ref(false)
const todoCount = ref<number | null>(null)
let todoRequestId = 0

function closeMobileMenuOnDesktop() {
  if (window.matchMedia('(min-width: 1024px)').matches) {
    mobileMenuOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', closeMobileMenuOnDesktop)
  window.addEventListener('apartment:tasks-updated', loadTodoCount)
  void loadTodoCount()
})

onUnmounted(() => {
  window.removeEventListener('resize', closeMobileMenuOnDesktop)
  window.removeEventListener('apartment:tasks-updated', loadTodoCount)
})

function changePage(page: PageKey) {
  mobileMenuOpen.value = false
  emit('change', page)
}

function logoutAndClose() {
  mobileMenuOpen.value = false
  void logout()
}

async function loadTodoCount() {
  const requestId = ++todoRequestId
  if (!hasPermission(pagePermissions.tasks)) {
    todoCount.value = null
    return
  }
  try {
    const count = (await api.tasks({ limit: 1, offset: 0 })).total
    if (requestId === todoRequestId) {
      todoCount.value = count
    }
  } catch {
    if (requestId === todoRequestId) {
      todoCount.value = null
    }
  }
}

watch(currentUser, () => {
  void loadTodoCount()
})

const builtInNavItems: Array<{ key: BuiltInPageKey; label: string; hint: string; icon: Component; permission: PermissionKey }> = [
  { key: 'dashboard', label: '管理控制台', hint: '运营驾驶舱', icon: Gauge, permission: pagePermissions.dashboard },
  { key: 'tasks', label: '通知提醒', hint: '风险与任务', icon: ClipboardList, permission: pagePermissions.tasks },
  { key: 'properties', label: '房源管理', hint: '楼栋与房间', icon: Building2, permission: pagePermissions.properties },
  { key: 'tenants', label: '租客列表', hint: '住户档案', icon: Users, permission: pagePermissions.tenants },
  { key: 'contracts', label: '合同管理', hint: '租约与签署', icon: FileText, permission: pagePermissions.contracts },
  { key: 'maintenance', label: '工单维修', hint: '报修处理', icon: Wrench, permission: pagePermissions.maintenance },
  { key: 'finance', label: '财务管理', hint: '账单与收支', icon: Landmark, permission: pagePermissions.finance },
  { key: 'reconciliation', label: '流水对账', hint: '银行流水', icon: ReceiptText, permission: pagePermissions.reconciliation },
  { key: 'auditLogs', label: '操作审计', hint: '关键动作留痕', icon: ListChecks, permission: pagePermissions.auditLogs },
  { key: 'permissions', label: '权限管理', hint: '角色与授权', icon: ShieldCheck, permission: pagePermissions.permissions },
]

const builtInPermissionKeys = new Set(builtInNavItems.map((item) => item.permission))
const dynamicNavItems = computed(() =>
  menuResources.value
    .filter((resource) => !builtInPermissionKeys.has(resource.key))
    .map((resource) => ({
      key: `custom:${resource.key}` as PageKey,
      label: resource.menu_label || resource.label,
      hint: resource.menu_hint || resource.description,
      icon: PanelTop,
      permission: resource.key,
    })),
)
const visibleNavItems = computed(() => [...builtInNavItems, ...dynamicNavItems.value].filter((item) => hasPermission(item.permission)))
</script>

<template>
  <div class="min-h-screen bg-surface text-slate-900">
    <aside
      :class="[
        'fixed inset-y-0 left-0 z-20 hidden flex-col bg-brand-900 text-white shadow-2xl shadow-brand-950/20 transition-all duration-300 lg:flex',
        sidebarCollapsed ? 'w-20' : 'w-[260px]',
      ]"
    >
      <div :class="['flex h-20 items-center gap-3 px-4', sidebarCollapsed ? 'justify-center' : 'justify-between']">
        <div v-if="!sidebarCollapsed" class="flex min-w-0 items-center gap-3">
          <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
            <Home class="h-6 w-6 text-emerald-300" />
          </div>
          <div class="min-w-0">
            <p class="text-lg font-bold tracking-tight">Propertied</p>
            <p class="text-xs font-medium text-slate-300">公寓运营系统</p>
          </div>
        </div>
        <button
          :class="[
            'hidden rounded-xl p-2 text-slate-300 transition hover:bg-white/10 hover:text-white lg:inline-flex',
            sidebarCollapsed ? 'h-11 w-11 items-center justify-center bg-white/10 ring-1 ring-white/15' : '',
          ]"
          type="button"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" class="h-5 w-5" />
          <PanelLeftClose v-else class="h-5 w-5" />
        </button>
      </div>

      <div v-if="demoAccountsEnabled && !sidebarCollapsed" class="px-4 pb-3">
        <label class="block text-xs font-semibold text-slate-400">演示账号</label>
        <select
          class="mt-2 h-10 w-full rounded-lg border border-white/10 bg-white/10 px-3 text-sm font-semibold text-white outline-none focus:ring-4 focus:ring-emerald-400/20"
          :value="currentRole"
          @change="setRole(($event.target as HTMLSelectElement).value as RoleKey)"
        >
          <option v-for="role in demoRoles" :key="role.key" class="text-slate-900" :value="role.key">
            {{ role.label }}
          </option>
        </select>
      </div>

      <nav class="sidebar-nav mt-2 flex-1 space-y-1 overflow-y-auto px-3 pb-3">
        <button
          v-for="item in visibleNavItems"
          :key="item.key"
          type="button"
          :class="[
            'group relative flex w-full items-center gap-3 rounded-xl py-3 text-left transition',
            sidebarCollapsed ? 'justify-center px-0' : 'px-3',
            props.currentPage === item.key
              ? 'bg-white/10 text-white'
              : 'text-slate-300 hover:bg-white/5 hover:text-white',
          ]"
          :title="sidebarCollapsed ? item.label : undefined"
          :data-testid="`desktop-nav-${item.key}`"
          @click="changePage(item.key)"
        >
          <span v-if="props.currentPage === item.key" class="absolute left-0 h-8 w-1 rounded-r-full bg-emerald-400" />
          <component :is="item.icon" :class="['h-5 w-5 shrink-0', sidebarCollapsed ? '' : 'ml-1']" />
          <span v-if="!sidebarCollapsed" class="min-w-0">
            <span class="block truncate text-sm font-semibold">{{ item.label }}</span>
            <span class="block truncate text-xs text-slate-400 group-hover:text-slate-300">{{ item.hint }}</span>
          </span>
        </button>
      </nav>

      <div :class="['m-4 rounded-2xl border border-white/10 bg-white/5 p-4', sidebarCollapsed ? 'space-y-3' : 'space-y-3']">
        <div :class="['flex items-center gap-3', sidebarCollapsed ? 'justify-center' : '']">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-200">
            <UserRound class="h-5 w-5" />
          </div>
          <div v-if="!sidebarCollapsed" class="min-w-0">
            <p class="truncate text-sm font-semibold">{{ currentUser?.name ?? '运营中心' }}</p>
            <p class="truncate text-xs text-slate-400">{{ currentUser?.role_label ?? '加载权限中' }} · 上海</p>
          </div>
        </div>
        <button v-if="!sidebarCollapsed" class="flex w-full items-center justify-center gap-2 rounded-xl bg-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/15 hover:text-white" type="button" @click="logout">
          <LogOut class="h-4 w-4" />退出登录
        </button>
      </div>
    </aside>

    <el-drawer v-model="mobileMenuOpen" direction="ltr" size="300px" :with-header="false" :body-style="{ padding: '0' }" class="lg:hidden">
      <div class="flex min-h-full flex-col bg-brand-900 text-white">
        <div class="flex h-16 items-center gap-3 px-5">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
            <Home class="h-5 w-5 text-emerald-300" />
          </div>
          <div>
            <p class="font-bold tracking-tight">Propertied</p>
            <p class="text-xs font-medium text-slate-300">公寓运营系统</p>
          </div>
        </div>

        <div v-if="demoAccountsEnabled" class="px-4 pb-3">
          <label class="block text-xs font-semibold text-slate-400">演示账号</label>
          <select
            class="mt-2 h-10 w-full rounded-lg border border-white/10 bg-white/10 px-3 text-sm font-semibold text-white outline-none focus:ring-4 focus:ring-emerald-400/20"
            :value="currentRole"
            @change="setRole(($event.target as HTMLSelectElement).value as RoleKey)"
          >
            <option v-for="role in demoRoles" :key="role.key" class="text-slate-900" :value="role.key">
              {{ role.label }}
            </option>
          </select>
        </div>

        <nav class="sidebar-nav mt-2 flex-1 space-y-1 overflow-y-auto px-3 pb-3">
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
            @click="changePage(item.key)"
          >
            <span v-if="props.currentPage === item.key" class="absolute left-0 h-8 w-1 rounded-r-full bg-emerald-400" />
            <component :is="item.icon" class="ml-1 h-5 w-5" />
            <span>
              <span class="block text-sm font-semibold">{{ item.label }}</span>
              <span class="block text-xs text-slate-400 group-hover:text-slate-300">{{ item.hint }}</span>
            </span>
          </button>
        </nav>

        <div class="m-4 space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-200">
              <UserRound class="h-5 w-5" />
            </div>
            <div>
              <p class="text-sm font-semibold">{{ currentUser?.name ?? '运营中心' }}</p>
              <p class="text-xs text-slate-400">{{ currentUser?.role_label ?? '加载权限中' }} · 上海</p>
            </div>
          </div>
          <button class="flex w-full items-center justify-center gap-2 rounded-xl bg-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/15 hover:text-white" type="button" @click="logoutAndClose">
            <LogOut class="h-4 w-4" />退出登录
          </button>
        </div>
      </div>
    </el-drawer>

    <div :class="['transition-all duration-300', sidebarCollapsed ? 'lg:pl-20' : 'lg:pl-[260px]']">
      <header class="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-slate-200/80 bg-surface/90 px-4 backdrop-blur sm:px-6 lg:h-20 lg:px-8">
        <div class="flex min-w-0 flex-1 items-center gap-3">
          <button class="rounded-xl p-2.5 text-slate-600 transition hover:bg-white hover:text-brand-900 lg:hidden" type="button" aria-label="打开导航菜单" @click="mobileMenuOpen = true">
            <Menu class="h-5 w-5" />
          </button>
        </div>
        <div class="flex shrink-0 items-center gap-2 sm:gap-3">
          <button v-if="hasPermission(pagePermissions.tasks)" class="secondary-button hidden sm:inline-flex" type="button" @click="changePage('tasks')">
            <ClipboardList class="h-4 w-4" />通知提醒{{ todoCount === null ? '' : ` ${todoCount}` }}
          </button>
          <button v-if="hasPermission(pagePermissions.permissions)" class="rounded-xl p-2.5 text-slate-500 transition hover:bg-white hover:text-brand-900" type="button" aria-label="权限管理" @click="changePage('permissions')">
            <Settings class="h-5 w-5" />
          </button>
        </div>
      </header>

      <main class="p-4 sm:p-6 lg:p-8">
        <slot />
      </main>
    </div>
  </div>
</template>
