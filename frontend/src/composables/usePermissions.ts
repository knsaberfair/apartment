import { computed, ref } from 'vue'
import { orderedPages, pagePermissions } from '@/config/permissions'
import { api, setDemoRoleHeader } from '@/services/api'
import type { CurrentUser, PermissionKey, RoleDefinition, RoleKey } from '@/types/auth'
import type { PageKey } from '@/types/navigation'

const currentRole = ref<RoleKey>('manager')
const currentUser = ref<CurrentUser | null>(null)
const roles = ref<RoleDefinition[]>([])
const loadingPermissions = ref(false)

const permissions = computed(() => new Set(currentUser.value?.permissions ?? []))

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

  function canViewPage(page: PageKey) {
    return hasPermission(pagePermissions[page])
  }

  function firstAllowedPage() {
    return orderedPages.find((page) => canViewPage(page)) ?? null
  }

  return {
    currentRole,
    currentUser,
    roles,
    loadingPermissions,
    permissions,
    loadCurrentUser,
    loadRoles,
    setRole,
    hasPermission,
    hasAnyPermission,
    canViewPage,
    firstAllowedPage,
  }
}
