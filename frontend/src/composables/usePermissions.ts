import { computed, ref } from 'vue'
import { orderedPages, pagePermissions } from '@/config/permissions'
import { api, setDemoRoleHeader } from '@/services/api'
import type { CurrentUser, PermissionKey, PermissionResource, RoleDefinition, RoleKey } from '@/types/auth'
import type { BuiltInPageKey, PageKey } from '@/types/navigation'

const currentRole = ref<RoleKey>('manager')
const currentUser = ref<CurrentUser | null>(null)
const roles = ref<RoleDefinition[]>([])
const permissionResources = ref<PermissionResource[]>([])
const loadingPermissions = ref(false)

const permissions = computed(() => new Set(currentUser.value?.permissions ?? []))
const menuResources = computed(() => permissionResources.value.filter((resource) => resource.type === 'menu'))

export function usePermissions() {
  async function loadCurrentUser() {
    loadingPermissions.value = true
    setDemoRoleHeader(currentRole.value)
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
    permissionResources.value = await api.permissionResources()
  }

  async function setRole(role: RoleKey) {
    currentRole.value = role
    setDemoRoleHeader(role)
    await loadCurrentUser()
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
    if (customPermission) {
      return hasPermission(customPermission)
    }
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
    permissionResources,
    menuResources,
    loadingPermissions,
    permissions,
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
