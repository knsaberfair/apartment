import type {
  CreatePermissionResourcePayload,
  CreateRolePayload,
  CurrentUser,
  DemoLoginPayload,
  LoginPayload,
  LoginResponse,
  PermissionGroup,
  PermissionKey,
  PermissionResource,
  RoleDefinition,
  RoleKey,
  UpdateRolePayload,
} from '@/types/auth'
import type {
  AuditLog,
  AuditLogParams,
  Contract,
  ContractCreatePayload,
  ContractRenewal,
  ContractRenewalRequest,
  ContractUpdatePayload,
  DashboardSummary,
  DepositSettlement,
  DepositSettlementRequest,
  FinanceTransaction,
  FinanceTransactionCreatePayload,
  MaintenanceAssignPayload,
  MaintenanceOrder,
  MaintenanceOrderCreatePayload,
  MoveOut,
  PaginatedResponse,
  PageParams,
  MoveOutRequest,
  Property,
  PropertyCreatePayload,
  PropertyOption,
  PropertyUpdatePayload,
  ReconciliationImportPayload,
  ReconciliationRecord,
  RentBillGeneratePayload,
  RentBillGenerateResult,
  TaskParams,
  Tenant,
  TenantCreatePayload,
  TenantUpdatePayload,
  TodoSummary,
} from '@/types/domain'

const REQUEST_OPTIONS: RequestInit = { credentials: 'include' }

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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)

  const response = await fetch(path, {
    ...REQUEST_OPTIONS,
    ...options,
    headers,
  })

  if (!response.ok) {
    let detail: unknown = null
    try {
      detail = await response.json()
    } catch {
      detail = response.statusText
    }

    const message = response.status === 403 ? '当前角色无权访问该资源' : response.status === 401 ? '请先登录' : `请求失败：${response.status} ${response.statusText}`
    throw new ApiError(message, response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && String(value).trim()) {
      search.set(key, String(value))
    }
  })
  return search.toString()
}

function pageQuery(params: PageParams = {}): string {
  return queryString({ limit: params.limit ?? 50, offset: params.offset ?? 0, q: params.q })
}

function jsonRequest<T>(path: string, method: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
}

async function downloadRequest(path: string): Promise<Blob> {
  const response = await fetch(path, REQUEST_OPTIONS)
  if (!response.ok) {
    let detail: unknown = null
    try {
      detail = await response.json()
    } catch {
      detail = response.statusText
    }
    const message = response.status === 403 ? '当前角色无权访问该资源' : response.status === 401 ? '请先登录' : `请求失败：${response.status} ${response.statusText}`
    throw new ApiError(message, response.status, detail)
  }
  return response.blob()
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export const api = {
  login: (payload: LoginPayload) => jsonRequest<LoginResponse>('/api/auth/login', 'POST', payload),
  demoLogin: (payload: DemoLoginPayload) => jsonRequest<LoginResponse>('/api/auth/demo-login', 'POST', payload),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  me: () => request<CurrentUser>('/api/auth/me'),
  roles: () => request<RoleDefinition[]>('/api/auth/roles'),
  permissionCatalog: () => request<PermissionGroup[]>('/api/permissions/catalog'),
  permissionResources: () => request<PermissionResource[]>('/api/permissions/resources'),
  permissionMenus: () => request<PermissionResource[]>('/api/permissions/menus'),
  createPermissionResource: (payload: CreatePermissionResourcePayload) => jsonRequest<PermissionResource>('/api/permissions/resources', 'POST', payload),
  updatePermissionResource: (key: PermissionKey, payload: CreatePermissionResourcePayload) => jsonRequest<PermissionResource>(`/api/permissions/resources/${encodeURIComponent(key)}`, 'PUT', payload),
  deletePermissionResource: (key: PermissionKey) => request<void>(`/api/permissions/resources/${encodeURIComponent(key)}`, { method: 'DELETE' }),
  permissionRoles: () => request<RoleDefinition[]>('/api/permissions/roles'),
  createRole: (payload: CreateRolePayload) => jsonRequest<RoleDefinition>('/api/permissions/roles', 'POST', payload),
  updateRole: (role: RoleKey, payload: UpdateRolePayload) => jsonRequest<RoleDefinition>(`/api/permissions/roles/${encodeURIComponent(role)}`, 'PUT', payload),
  deleteRole: (role: RoleKey) => request<void>(`/api/permissions/roles/${encodeURIComponent(role)}`, { method: 'DELETE' }),
  updateRolePermissions: (role: RoleKey, permissions: PermissionKey[]) => jsonRequest<RoleDefinition>(`/api/permissions/roles/${encodeURIComponent(role)}/permissions`, 'PUT', { permissions }),
  dashboard: () => request<DashboardSummary>('/api/dashboard/summary'),
  exportDashboard: () => downloadRequest('/api/dashboard/export'),
  tasks: (params: TaskParams = {}) => request<TodoSummary>(`/api/tasks?${queryString({ limit: params.limit ?? 50, offset: params.offset ?? 0, q: params.q, source: params.source, severity: params.severity })}`),
  auditLogs: (params: AuditLogParams = {}) => request<PaginatedResponse<AuditLog>>(`/api/audit-logs?${queryString({ limit: params.limit ?? 50, offset: params.offset ?? 0, q: params.q, actor_id: params.actor_id, actor_role: params.actor_role, action: params.action, resource_type: params.resource_type, resource_id: params.resource_id, created_from: params.created_from, created_to: params.created_to })}`),
  properties: (params: PageParams = {}) => request<PaginatedResponse<Property>>(`/api/properties?${pageQuery(params)}`),
  createProperty: (payload: PropertyCreatePayload) => jsonRequest<Property>('/api/properties', 'POST', payload),
  updateProperty: (id: string, payload: PropertyUpdatePayload) => jsonRequest<Property>(`/api/properties/${encodeURIComponent(id)}`, 'PUT', payload),
  deleteProperty: (id: string) => request<void>(`/api/properties/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  tenantPropertyOptions: () => request<Property[]>('/api/tenants/property-options'),
  tenants: (params: PageParams = {}) => request<PaginatedResponse<Tenant>>(`/api/tenants?${pageQuery(params)}`),
  createTenant: (payload: TenantCreatePayload) => jsonRequest<Tenant>('/api/tenants', 'POST', payload),
  updateTenant: (id: string, payload: TenantUpdatePayload) => jsonRequest<Tenant>(`/api/tenants/${encodeURIComponent(id)}`, 'PUT', payload),
  deleteTenant: (id: string) => request<void>(`/api/tenants/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  contracts: (params: PageParams = {}) => request<PaginatedResponse<Contract>>(`/api/contracts?${pageQuery(params)}`),
  contractPropertyOptions: () => request<Property[]>('/api/contracts/property-options'),
  createContract: (payload: ContractCreatePayload) => jsonRequest<Contract>('/api/contracts', 'POST', payload),
  updateContract: (id: string, payload: ContractUpdatePayload) => jsonRequest<Contract>(`/api/contracts/${encodeURIComponent(id)}`, 'PUT', payload),
  approveContract: (id: string) => jsonRequest<Contract>(`/api/contracts/${encodeURIComponent(id)}/approve`, 'POST', {}),
  terminateContract: (id: string) => jsonRequest<Contract>(`/api/contracts/${encodeURIComponent(id)}/terminate`, 'POST', {}),
  contractRenewals: (contractId: string) => request<ContractRenewal[]>(`/api/contracts/${encodeURIComponent(contractId)}/renewals`),
  renewContract: (contractId: string, payload: ContractRenewalRequest) => jsonRequest<ContractRenewal>(`/api/contracts/${encodeURIComponent(contractId)}/renew`, 'POST', payload),
  contractMoveOuts: (contractId: string) => request<MoveOut[]>(`/api/contracts/${encodeURIComponent(contractId)}/move-outs`),
  createMoveOut: (contractId: string, payload: MoveOutRequest) => jsonRequest<MoveOut>(`/api/contracts/${encodeURIComponent(contractId)}/move-out`, 'POST', payload),
  moveOutSettlements: (moveOutId: string) => request<DepositSettlement[]>(`/api/contracts/move-outs/${encodeURIComponent(moveOutId)}/settlements`),
  settleMoveOut: (moveOutId: string, payload: DepositSettlementRequest) => jsonRequest<DepositSettlement>(`/api/contracts/move-outs/${encodeURIComponent(moveOutId)}/settle`, 'POST', payload),
  maintenancePropertyOptions: () => request<PropertyOption[]>('/api/maintenance-orders/property-options'),
  maintenanceOrders: (params: PageParams = {}) => request<PaginatedResponse<MaintenanceOrder>>(`/api/maintenance-orders?${pageQuery(params)}`),
  createMaintenanceOrder: (payload: MaintenanceOrderCreatePayload) => jsonRequest<MaintenanceOrder>('/api/maintenance-orders', 'POST', payload),
  assignMaintenanceOrder: (id: string, payload: MaintenanceAssignPayload) => jsonRequest<MaintenanceOrder>(`/api/maintenance-orders/${encodeURIComponent(id)}/assign`, 'POST', payload),
  resolveMaintenanceOrder: (id: string) => jsonRequest<MaintenanceOrder>(`/api/maintenance-orders/${encodeURIComponent(id)}/resolve`, 'POST', {}),
  transactions: (params: PageParams = {}) => request<PaginatedResponse<FinanceTransaction>>(`/api/finance/transactions?${pageQuery(params)}`),
  financePropertyOptions: () => request<PropertyOption[]>('/api/finance/transactions/property-options'),
  createTransaction: (payload: FinanceTransactionCreatePayload) => jsonRequest<FinanceTransaction>('/api/finance/transactions', 'POST', payload),
  confirmTransaction: (id: string) => jsonRequest<FinanceTransaction>(`/api/finance/transactions/${encodeURIComponent(id)}/confirm`, 'POST', {}),
  generateRentBills: (payload: RentBillGeneratePayload) => jsonRequest<RentBillGenerateResult>('/api/finance/rent-bills/generate', 'POST', payload),
  exportTransactions: () => downloadRequest('/api/finance/transactions/export'),
  reconciliation: (params: PageParams = {}) => request<PaginatedResponse<ReconciliationRecord>>(`/api/finance/reconciliation?${pageQuery(params)}`),
  importReconciliation: (payload: ReconciliationImportPayload) => jsonRequest<ReconciliationRecord[]>('/api/finance/reconciliation/import', 'POST', payload),
  retryReconciliation: (id: string) => jsonRequest<ReconciliationRecord>(`/api/finance/reconciliation/${encodeURIComponent(id)}/retry-match`, 'POST', {}),
  resolveReconciliation: (id: string) => jsonRequest<ReconciliationRecord>(`/api/finance/reconciliation/${encodeURIComponent(id)}/resolve`, 'POST', {}),
  exportReconciliation: () => downloadRequest('/api/finance/reconciliation/export'),
  exportDepositSettlements: () => downloadRequest('/api/finance/settlements/export'),
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
