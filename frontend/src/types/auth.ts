import type { BuiltInPageKey } from '@/types/navigation'

export type BuiltInRoleKey = 'super_admin' | 'manager' | 'leasing_agent' | 'maintenance_staff' | 'finance_staff' | 'viewer'
export type RoleKey = BuiltInRoleKey | (string & {})

export type BuiltInPermissionKey =
  | 'dashboard:view'
  | 'dashboard:export'
  | 'properties:view'
  | 'properties:create'
  | 'properties:update'
  | 'properties:delete'
  | 'tenants:view'
  | 'tenants:create'
  | 'tenants:update'
  | 'tenants:delete'
  | 'contracts:view'
  | 'contracts:create'
  | 'contracts:approve'
  | 'contracts:terminate'
  | 'maintenance:view'
  | 'maintenance:create'
  | 'maintenance:assign'
  | 'maintenance:resolve'
  | 'finance:view'
  | 'finance:create'
  | 'finance:export'
  | 'reconciliation:view'
  | 'reconciliation:import'
  | 'reconciliation:export'
  | 'permissions:view'
  | 'permissions:manage'
  | 'system:settings'
  | 'tasks:view'

export type PermissionKey = BuiltInPermissionKey | (string & {})
export type PermissionResourceType = 'menu' | 'button' | 'api'

export interface CurrentUser {
  id: string
  name: string
  role: RoleKey
  role_label: string
  permissions: PermissionKey[]
}

export interface RoleDefinition {
  key: RoleKey
  label: string
  permissions: PermissionKey[]
}

export interface PermissionDefinition {
  key: PermissionKey
  label: string
  description: string
  type?: PermissionResourceType
  route?: string
  menu_label?: string
  menu_hint?: string
  built_in?: boolean
}

export interface PermissionGroup {
  key: string
  label: string
  permissions: PermissionDefinition[]
}

export interface PermissionResource {
  key: PermissionKey
  label: string
  description: string
  group: string
  group_label: string
  type: PermissionResourceType
  route?: string | null
  menu_label?: string | null
  menu_hint?: string | null
  sort?: number
  built_in?: boolean
}

export interface UpdateRolePermissionsPayload {
  permissions: PermissionKey[]
}

export interface CreateRolePayload {
  key: string
  label: string
  permissions: PermissionKey[]
}

export interface CreatePermissionResourcePayload {
  key: string
  label: string
  description: string
  group: string
  group_label: string
  type: PermissionResourceType
  route?: string | null
  menu_label?: string | null
  menu_hint?: string | null
  sort?: number | null
}

export type PagePermissionMap = Record<BuiltInPageKey, PermissionKey>
