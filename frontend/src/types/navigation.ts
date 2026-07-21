export type BuiltInPageKey =
  | 'dashboard'
  | 'tasks'
  | 'properties'
  | 'tenants'
  | 'contracts'
  | 'maintenance'
  | 'finance'
  | 'reconciliation'
  | 'auditLogs'
  | 'permissions'

export type CustomPageKey = `custom:${string}`
export type PageKey = BuiltInPageKey | CustomPageKey

export const builtInPagePaths: Record<BuiltInPageKey, string> = {
  dashboard: '/dashboard',
  tasks: '/tasks',
  properties: '/properties',
  tenants: '/tenants',
  contracts: '/contracts',
  maintenance: '/maintenance',
  finance: '/finance',
  reconciliation: '/reconciliation',
  auditLogs: '/audit-logs',
  permissions: '/permissions',
}

export function pageToPath(page: PageKey) {
  if (page.startsWith('custom:')) {
    return `/custom/${encodeURIComponent(page.slice('custom:'.length))}`
  }
  return builtInPagePaths[page as BuiltInPageKey]
}

export function customPageFromResourceKey(resourceKey: string): CustomPageKey {
  return `custom:${resourceKey}`
}
