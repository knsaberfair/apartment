<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import ForbiddenState from '@/components/ui/ForbiddenState.vue'
import CustomResourcePage from '@/pages/CustomResourcePage.vue'
import { usePermissions } from '@/composables/usePermissions'
import { pageFromRoute } from '@/router'
import { pageToPath, type PageKey } from '@/types/navigation'

const route = useRoute()
const router = useRouter()
const {
  canViewPage,
  firstAllowedPage,
  getMenuResourceByPage,
  restoreSession,
  authReady,
  loadingPermissions,
  currentUser,
  isAuthenticated,
} = usePermissions()

const currentPage = computed<PageKey>(() => pageFromRoute(route) ?? 'dashboard')
const hasAnyPage = computed(() => firstAllowedPage() !== null)
const isLoginPage = computed(() => route.name === 'login')
const isCustomPage = computed(() => currentPage.value.startsWith('custom:'))
const currentCustomResource = computed(() => getMenuResourceByPage(currentPage.value))

function navigate(page: PageKey) {
  if (!canViewPage(page)) return
  void router.push(pageToPath(page))
}

function ensureAllowedRoute() {
  if (!isAuthenticated.value || isLoginPage.value) return
  if (canViewPage(currentPage.value)) return

  const allowedPage = firstAllowedPage()
  if (allowedPage) {
    void router.replace(pageToPath(allowedPage))
  }
}

function resolveLoginRedirect() {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : null
  if (redirect && redirect.startsWith('/') && !redirect.startsWith('//') && !redirect.startsWith('/login')) {
    const resolved = router.resolve(redirect)
    const page = pageFromRoute(resolved)
    if (page && canViewPage(page)) {
      return redirect
    }
  }

  const allowedPage = firstAllowedPage()
  return allowedPage ? pageToPath(allowedPage) : '/'
}

async function handleLoginSuccess() {
  await router.replace(resolveLoginRedirect())
}

onMounted(async () => {
  if (!authReady.value) {
    await restoreSession()
  }
  if (route.name === 'login' && isAuthenticated.value) {
    await handleLoginSuccess()
  }
})

watch(isAuthenticated, (authenticated) => {
  if (!authenticated && route.name !== 'login') {
    void router.replace('/login')
  }
})

watch(currentUser, ensureAllowedRoute)
watch(currentPage, ensureAllowedRoute)
</script>

<template>
  <div v-if="!authReady" class="min-h-screen bg-surface p-8 text-sm text-slate-500">正在恢复登录状态...</div>
  <RouterView v-else-if="isLoginPage" v-slot="{ Component }">
    <component :is="Component" @success="handleLoginSuccess" />
  </RouterView>
  <AppShell v-else :current-page="currentPage" @change="navigate">
    <div v-if="loadingPermissions" class="panel p-8 text-sm text-slate-500">正在加载角色权限...</div>
    <ForbiddenState v-else-if="!hasAnyPage" title="403 无可访问页面" description="当前账号没有任何页面访问权限，请切换账号或联系系统管理员。" />
    <CustomResourcePage v-else-if="isCustomPage" :resource="currentCustomResource" />
    <RouterView v-else v-slot="{ Component }">
      <component :is="Component" />
    </RouterView>
  </AppShell>
</template>
