import { computed, ref } from 'vue'
import { orderedPages, pagePermissions } from '@/config/permissions'
import { api } from '@/services/api'
import type { CurrentUser, PermissionKey, PermissionResource, RoleDefinition, RoleKey } from '@/types/auth'
import type { BuiltInPageKey, PageKey } from '@/types/navigation'

const currentUser = ref<CurrentUser | null>(null)
const roles = ref<RoleDefinition[]>([])
const permissionResources = ref<PermissionResource[]>([])
const loadingPermissions = ref(false)
const authReady = ref(false)

const permissions = computed(() => new Set(currentUser.value?.permissions ?? []))
const menuResources = computed(() => permissionResources.value.filter((resource) => resource.type === 'menu'))
const currentRole = computed<RoleKey>(() => currentUser.value?.role ?? 'viewer')
const isAuthenticated = computed(() => currentUser.value !== null)

export const demoAccountsEnabled = import.meta.env.VITE_ENABLE_DEMO_ACCOUNTS === 'true'
const demoRoleKeys = demoAccountsEnabled ? new Set(['super_admin', 'manager', 'leasing_agent', 'maintenance_staff', 'finance_staff', 'viewer']) : new Set<string>()
const demoRoles = computed(() => roles.value.filter((role) => demoRoleKeys.has(role.key)))

export function usePermissions() {
  async function loadCurrentUser() {
    loadingPermissions.value = true
    try {
      currentUser.value = await api.me()
    } finally {
      loadingPermissions.value = false
    }
  }

  async function loadRoles() {
    roles.value = await api.roles()
  }

  async function refreshRoles() {
    roles.value = await api.permissionRoles()
  }

  async function loadPermissionResources() {
    permissionResources.value = await api.permissionMenus()
  }

  async function refreshPermissionResources() {
    permissionResources.value = await api.permissionMenus()
  }

  async function login(username: string, password: string) {
    loadingPermissions.value = true
    try {
      const response = await api.login({ username, password })
      currentUser.value = response.user
      await Promise.all([loadRoles(), loadPermissionResources()])
    } finally {
      loadingPermissions.value = false
      authReady.value = true
    }
  }

  async function restoreSession() {
    loadingPermissions.value = true
    try {
      currentUser.value = await api.me()
      await Promise.all([loadRoles(), loadPermissionResources()])
    } catch {
      currentUser.value = null
      roles.value = []
      permissionResources.value = []
    } finally {
      loadingPermissions.value = false
      authReady.value = true
    }
  }

  async function logout() {
    await api.logout()
    currentUser.value = null
    roles.value = []
    permissionResources.value = []
  }

  async function setRole(role: RoleKey) {
    if (!demoAccountsEnabled || !demoRoleKeys.has(role)) return

    loadingPermissions.value = true
    try {
      const response = await api.demoLogin({ role })
      currentUser.value = response.user
      await Promise.all([loadRoles(), loadPermissionResources()])
    } finally {
      loadingPermissions.value = false
      authReady.value = true
    }
  }

  function hasPermission(permission?: PermissionKey) {
    if (!permission) return true
    return permissions.value.has(permission)
  }

  function hasAnyPermission(requiredPermissions: PermissionKey[]) {
    return requiredPermissions.some((permission) => hasPermission(permission))
  }

  function getCustomPermissionFromPage(page: PageKey) {
    return page.startsWith('custom:') ? page.slice('custom:'.length) : null
  }

  function canViewPage(page: PageKey) {
    const customPermission = getCustomPermissionFromPage(page)
    if (customPermission !== null) {
      return menuResources.value.some((resource) => resource.key === customPermission && hasPermission(resource.key))
    }
    if (!Object.prototype.hasOwnProperty.call(pagePermissions, page)) return false
    return hasPermission(pagePermissions[page as BuiltInPageKey])
  }

  function firstAllowedPage() {
    const builtInPage = orderedPages.find((page) => canViewPage(page))
    if (builtInPage) return builtInPage
    const customMenu = menuResources.value.find((resource) => hasPermission(resource.key))
    return customMenu ? (`custom:${customMenu.key}` as PageKey) : null
  }

  function getMenuResourceByPage(page: PageKey) {
    const customPermission = getCustomPermissionFromPage(page)
    if (!customPermission) return null
    return menuResources.value.find((resource) => resource.key === customPermission) ?? null
  }

  return {
    currentRole,
    currentUser,
    roles,
    demoAccountsEnabled,
    demoRoles,
    permissionResources,
    menuResources,
    loadingPermissions,
    authReady,
    isAuthenticated,
    permissions,
    login,
    logout,
    restoreSession,
    loadCurrentUser,
    loadRoles,
    refreshRoles,
    loadPermissionResources,
    refreshPermissionResources,
    setRole,
    hasPermission,
    hasAnyPermission,
    canViewPage,
    firstAllowedPage,
    getMenuResourceByPage,
  }
}
