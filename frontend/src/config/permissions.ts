import type { PageKey } from '@/types/navigation'
import type { PagePermissionMap, PermissionKey } from '@/types/auth'

export const pagePermissions: PagePermissionMap = {
  dashboard: 'dashboard:view',
  properties: 'properties:view',
  tenants: 'tenants:view',
  contracts: 'contracts:view',
  maintenance: 'maintenance:view',
  finance: 'finance:view',
  reconciliation: 'reconciliation:view',
}

export const orderedPages: PageKey[] = [
  'dashboard',
  'properties',
  'tenants',
  'contracts',
  'maintenance',
  'finance',
  'reconciliation',
]

export const pageActionPermissions = {
  dashboardExport: 'dashboard:export',
  propertyCreate: 'properties:create',
  tenantCreate: 'tenants:create',
  contractCreate: 'contracts:create',
  maintenanceCreate: 'maintenance:create',
  financeCreate: 'finance:create',
  reconciliationImport: 'reconciliation:import',
  reconciliationExport: 'reconciliation:export',
  tasksView: 'tasks:view',
  systemSettings: 'system:settings',
} satisfies Record<string, PermissionKey>
