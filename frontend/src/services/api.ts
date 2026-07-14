import type { CurrentUser, RoleDefinition, RoleKey } from '@/types/auth'
import type {
  Contract,
  DashboardSummary,
  FinanceTransaction,
  MaintenanceOrder,
  Property,
  ReconciliationRecord,
  Tenant,
} from '@/types/domain'

let demoRole: RoleKey = 'manager'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function setDemoRoleHeader(role: RoleKey) {
  demoRole = role
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'X-Demo-Role': demoRole,
    },
  })

  if (!response.ok) {
    let detail: unknown = null
    try {
      detail = await response.json()
    } catch {
      detail = response.statusText
    }

    const message = response.status === 403 ? '当前角色无权访问该资源' : `请求失败：${response.status} ${response.statusText}`
    throw new ApiError(message, response.status, detail)
  }

  return response.json() as Promise<T>
}

export const api = {
  me: () => request<CurrentUser>('/api/auth/me'),
  roles: () => request<RoleDefinition[]>('/api/auth/roles'),
  dashboard: () => request<DashboardSummary>('/api/dashboard/summary'),
  properties: () => request<Property[]>('/api/properties'),
  tenants: () => request<Tenant[]>('/api/tenants'),
  contracts: () => request<Contract[]>('/api/contracts'),
  maintenanceOrders: () => request<MaintenanceOrder[]>('/api/maintenance-orders'),
  transactions: () => request<FinanceTransaction[]>('/api/finance/transactions'),
  reconciliation: () => request<ReconciliationRecord[]>('/api/finance/reconciliation'),
}

export function currency(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(value)
}

export function compactCurrency(value: number): string {
  if (Math.abs(value) >= 10000) {
    return `¥${(value / 10000).toFixed(1)}万`
  }
  return currency(value)
}
