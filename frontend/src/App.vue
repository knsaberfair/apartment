<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import ForbiddenState from '@/components/ui/ForbiddenState.vue'
import Contracts from '@/pages/Contracts.vue'
import CustomResourcePage from '@/pages/CustomResourcePage.vue'
import Dashboard from '@/pages/Dashboard.vue'
import Finance from '@/pages/Finance.vue'
import Maintenance from '@/pages/Maintenance.vue'
import PermissionManagement from '@/pages/PermissionManagement.vue'
import Properties from '@/pages/Properties.vue'
import Reconciliation from '@/pages/Reconciliation.vue'
import Tenants from '@/pages/Tenants.vue'
import { usePermissions } from '@/composables/usePermissions'
import type { BuiltInPageKey, PageKey } from '@/types/navigation'

const currentPage = ref<PageKey>('dashboard')
const {
  canViewPage,
  firstAllowedPage,
  getMenuResourceByPage,
  loadCurrentUser,
  loadPermissionResources,
  loadRoles,
  loadingPermissions,
  currentUser,
} = usePermissions()

const pages: Record<BuiltInPageKey, unknown> = {
  dashboard: Dashboard,
  properties: Properties,
  tenants: Tenants,
  contracts: Contracts,
  maintenance: Maintenance,
  finance: Finance,
  reconciliation: Reconciliation,
  permissions: PermissionManagement,
}

const isCustomPage = computed(() => currentPage.value.startsWith('custom:'))
const currentComponent = computed(() => (isCustomPage.value ? null : pages[currentPage.value as BuiltInPageKey]))
const currentCustomResource = computed(() => getMenuResourceByPage(currentPage.value))
const hasAnyPage = computed(() => firstAllowedPage() !== null)

function navigate(page: PageKey) {
  if (canViewPage(page)) {
    currentPage.value = page
  }
}

function ensureAllowedPage() {
  if (!currentUser.value) return
  if (!canViewPage(currentPage.value)) {
    const allowedPage = firstAllowedPage()
    if (allowedPage) {
      currentPage.value = allowedPage
    }
  }
}

onMounted(async () => {
  await Promise.all([loadCurrentUser(), loadRoles(), loadPermissionResources()])
  ensureAllowedPage()
})

watch(currentUser, ensureAllowedPage)
</script>

<template>
  <AppShell :current-page="currentPage" @change="navigate">
    <div v-if="loadingPermissions" class="panel p-8 text-sm text-slate-500">正在加载角色权限...</div>
    <ForbiddenState v-else-if="!hasAnyPage" title="403 无可访问页面" description="当前角色没有任何页面访问权限，请切换角色或联系系统管理员。" />
    <CustomResourcePage v-else-if="isCustomPage" :resource="currentCustomResource" />
    <component v-else :is="currentComponent" />
  </AppShell>
</template>
