import type { PageKey } from '@/types/navigation'

export type RoleKey = 'super_admin' | 'manager' | 'leasing_agent' | 'maintenance_staff' | 'finance_staff' | 'viewer'

export type PermissionKey =
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
}

export interface PermissionGroup {
  key: string
  label: string
  permissions: PermissionDefinition[]
}

export interface UpdateRolePermissionsPayload {
  permissions: PermissionKey[]
}

export type PagePermissionMap = Record<PageKey, PermissionKey>
