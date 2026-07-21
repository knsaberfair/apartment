import type { PageKey } from '@/types/navigation'
import type { PagePermissionMap, PermissionKey } from '@/types/auth'

export const pagePermissions: PagePermissionMap = {
  dashboard: 'dashboard:view',
  tasks: 'tasks:view',
  properties: 'properties:view',
  tenants: 'tenants:view',
  contracts: 'contracts:view',
  maintenance: 'maintenance:view',
  finance: 'finance:view',
  reconciliation: 'reconciliation:view',
  auditLogs: 'audit:view',
  permissions: 'permissions:view',
}

export const orderedPages: PageKey[] = [
  'dashboard',
  'tasks',
  'properties',
  'tenants',
  'contracts',
  'maintenance',
  'finance',
  'reconciliation',
  'auditLogs',
  'permissions',
]

export const pageActionPermissions = {
  dashboardExport: 'dashboard:export',
  propertyCreate: 'properties:create',
  propertyUpdate: 'properties:update',
  propertyDelete: 'properties:delete',
  tenantCreate: 'tenants:create',
  tenantUpdate: 'tenants:update',
  tenantDelete: 'tenants:delete',
  contractCreate: 'contracts:create',
  contractApprove: 'contracts:approve',
  contractTerminate: 'contracts:terminate',
  maintenanceCreate: 'maintenance:create',
  maintenanceAssign: 'maintenance:assign',
  maintenanceResolve: 'maintenance:resolve',
  financeCreate: 'finance:create',
  financeConfirm: 'finance:confirm',
  financeExport: 'finance:export',
  reconciliationImport: 'reconciliation:import',
  reconciliationResolve: 'reconciliation:resolve',
  reconciliationExport: 'reconciliation:export',
  permissionManage: 'permissions:manage',
  tasksView: 'tasks:view',
  systemSettings: 'system:settings',
} satisfies Record<string, PermissionKey>
