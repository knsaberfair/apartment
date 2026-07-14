export type BuiltInPageKey =
  | 'dashboard'
  | 'properties'
  | 'tenants'
  | 'contracts'
  | 'maintenance'
  | 'finance'
  | 'reconciliation'
  | 'permissions'

export type CustomPageKey = `custom:${string}`
export type PageKey = BuiltInPageKey | CustomPageKey
