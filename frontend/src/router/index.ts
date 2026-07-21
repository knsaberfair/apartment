import { createRouter, createWebHistory } from 'vue-router'
import { usePermissions } from '@/composables/usePermissions'
import { customPageFromResourceKey, pageToPath, type BuiltInPageKey, type PageKey } from '@/types/navigation'

declare module 'vue-router' {
  interface RouteMeta {
    pageKey?: BuiltInPageKey
    public?: boolean
  }
}

const PAGE_STORAGE_KEY = 'apartment_current_page'

export function pageFromRoute(route: { meta?: { pageKey?: BuiltInPageKey }; name?: unknown; params?: Record<string, unknown> }): PageKey | null {
  if (route.meta?.pageKey) return route.meta.pageKey
  if (route.name === 'custom') {
    const resourceKey = route.params?.resourceKey
    if (typeof resourceKey === 'string') return customPageFromResourceKey(resourceKey)
    if (Array.isArray(resourceKey) && resourceKey[0]) return customPageFromResourceKey(resourceKey[0])
  }
  return null
}

function storedPage() {
  try {
    return localStorage.getItem(PAGE_STORAGE_KEY) as PageKey | null
  } catch {
    return null
  }
}

function safeRedirectPath(redirect: unknown) {
  if (typeof redirect !== 'string') return null
  if (!redirect.startsWith('/') || redirect.startsWith('//') || redirect.startsWith('/login')) return null
  return redirect
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/pages/Dashboard.vue') },
    { path: '/login', name: 'login', component: () => import('@/pages/Login.vue'), meta: { public: true } },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/pages/Dashboard.vue'), meta: { pageKey: 'dashboard' } },
    { path: '/tasks', name: 'tasks', component: () => import('@/pages/Tasks.vue'), meta: { pageKey: 'tasks' } },
    { path: '/properties', name: 'properties', component: () => import('@/pages/Properties.vue'), meta: { pageKey: 'properties' } },
    { path: '/tenants', name: 'tenants', component: () => import('@/pages/Tenants.vue'), meta: { pageKey: 'tenants' } },
    { path: '/contracts', name: 'contracts', component: () => import('@/pages/Contracts.vue'), meta: { pageKey: 'contracts' } },
    { path: '/maintenance', name: 'maintenance', component: () => import('@/pages/Maintenance.vue'), meta: { pageKey: 'maintenance' } },
    { path: '/finance', name: 'finance', component: () => import('@/pages/Finance.vue'), meta: { pageKey: 'finance' } },
    { path: '/reconciliation', name: 'reconciliation', component: () => import('@/pages/Reconciliation.vue'), meta: { pageKey: 'reconciliation' } },
    { path: '/audit-logs', name: 'auditLogs', component: () => import('@/pages/AuditLogs.vue'), meta: { pageKey: 'auditLogs' } },
    { path: '/permissions', name: 'permissions', component: () => import('@/pages/PermissionManagement.vue'), meta: { pageKey: 'permissions' } },
    { path: '/custom/:resourceKey', name: 'custom', component: () => import('@/pages/CustomResourcePage.vue') },
    { path: '/:pathMatch(.*)*', name: 'notFound', component: () => import('@/pages/Dashboard.vue') },
  ],
})

let restorePromise: Promise<void> | null = null

async function ensureAuthReady() {
  const { authReady, restoreSession } = usePermissions()
  if (authReady.value) return
  restorePromise ??= restoreSession()
  await restorePromise
}

router.beforeEach(async (to) => {
  const { authReady, isAuthenticated, canViewPage, firstAllowedPage } = usePermissions()
  if (!authReady.value) {
    await ensureAuthReady()
  }

  if (to.meta.public) {
    if (to.name !== 'login' || !isAuthenticated.value) return true

    const redirectPath = safeRedirectPath(to.query.redirect)
    if (redirectPath) {
      const resolved = router.resolve(redirectPath)
      const redirectPage = pageFromRoute(resolved)
      if (redirectPage && canViewPage(redirectPage)) return redirectPath
    }

    const allowedPage = firstAllowedPage()
    return allowedPage ? pageToPath(allowedPage) : '/'
  }

  if (!isAuthenticated.value) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'home' || to.name === 'notFound') {
    const legacyPage = storedPage()
    if (legacyPage && canViewPage(legacyPage)) return pageToPath(legacyPage)

    const allowedPage = firstAllowedPage()
    return allowedPage ? pageToPath(allowedPage) : true
  }

  const page = pageFromRoute(to)
  if (page && canViewPage(page)) return true

  const allowedPage = firstAllowedPage()
  return allowedPage ? pageToPath(allowedPage) : true
})

export default router
