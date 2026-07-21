export interface MetricCard {
  label: string
  value: string
  change: string
  tone: 'primary' | 'success' | 'warning' | 'danger'
}

export interface DashboardSummary {
  metrics: MetricCard[]
  occupancy_rate: number
  monthly_income: number
  pending_tasks: number
  expiring_contracts: number
  recent_contracts: Contract[]
  urgent_work_orders: MaintenanceOrder[]
  income_trend: Array<{ month: string; income: number }>
}

export type TodoSeverity = 'info' | 'warning' | 'danger'
export type TodoSource = 'contracts' | 'maintenance' | 'finance' | 'reconciliation'

export interface TodoItem {
  id: string
  source: TodoSource
  source_id: string
  title: string
  description: string
  due_date: string | null
  severity: TodoSeverity
  status: string
  assignee: string | null
  related_room: string | null
  related_person: string | null
}

export interface TodoSummary {
  total: number
  urgent: number
  overdue: number
  items: TodoItem[]
  limit?: number
  offset?: number
}

export type PropertyStatus = 'occupied' | 'vacant' | 'reserved' | 'maintenance'

export interface Property {
  id: string
  building: string
  room: string
  layout: string
  area: number
  rent: number
  status: PropertyStatus
  tenant: string | null
  lease_end: string | null
  tags: string[]
}

export interface PropertyCreatePayload {
  id: string
  building: string
  room: string
  layout: string
  area: number
  rent: number
  status: PropertyStatus
  tenant: string | null
  lease_end: string | null
  tags: string[]
}

export type PropertyUpdatePayload = Omit<PropertyCreatePayload, 'id'>

export interface PropertyOption {
  id: string
  building: string
  room: string
}

export type PaymentStatus = 'paid' | 'pending' | 'overdue' | 'reconciled'

export type TenantStatus = 'active' | 'moved_out'

export interface Tenant {
  id: string
  property_id: string
  name: string
  phone: string
  room: string
  contract_id: string
  payment_status: PaymentStatus
  move_in_date: string
  lease_end: string
  balance: number
  status: TenantStatus
  move_out_date: string | null
}

export interface TenantCreatePayload {
  id: string
  property_id: string
  name: string
  phone: string
  contract_id: string
  payment_status: PaymentStatus
  move_in_date: string
  lease_end: string
  balance: number
}

export type TenantUpdatePayload = Omit<TenantCreatePayload, 'id'>

export type ContractStatus = 'active' | 'expiring' | 'pending' | 'terminated'

export interface Contract {
  id: string
  property_id: string
  tenant: string
  room: string
  start_date: string
  end_date: string
  monthly_rent: number
  deposit: number
  status: ContractStatus
  days_left: number
}

export interface ContractCreatePayload {
  id: string
  property_id: string
  tenant: string
  start_date: string
  end_date: string
  monthly_rent: number
  deposit: number
}

export type ContractUpdatePayload = Omit<ContractCreatePayload, 'id'>

export interface ContractRenewalRequest {
  new_end_date: string
  monthly_rent: number
  deposit: number
}

export interface ContractRenewal {
  id: string
  contract_id: string
  old_end_date: string
  new_end_date: string
  monthly_rent: number
  deposit: number
  created_at: string
}

export interface MoveOutRequest {
  move_out_date: string
  reason: string
}

export interface MoveOut {
  id: string
  contract_id: string
  property_id: string
  tenant: string
  room: string
  move_out_date: string
  reason: string
  status: string
  created_at: string
}

export interface DepositSettlementRequest {
  deductions: number
  rent_deduction: number
  utility_deduction: number
  damage_deduction: number
  cleaning_deduction: number
  other_deduction: number
  settled_date: string
  method: string
  note: string
}

export interface DepositSettlement {
  id: string
  move_out_id: string
  contract_id: string
  property_id: string
  tenant: string
  room: string
  deposit: number
  deductions: number
  rent_deduction: number
  utility_deduction: number
  damage_deduction: number
  cleaning_deduction: number
  other_deduction: number
  refund_amount: number
  settled_date: string
  status: string
  method: string
  note: string
  finance_transaction_id: string | null
}

export type MaintenancePriority = 'low' | 'medium' | 'high' | 'urgent'
export type MaintenanceStatus = 'open' | 'in_progress' | 'resolved'

export interface MaintenanceOrder {
  id: string
  property_id: string
  title: string
  room: string
  tenant: string
  category: string
  priority: MaintenancePriority
  status: MaintenanceStatus
  assignee: string
  created_at: string
  due_at: string
}

export interface MaintenanceOrderCreatePayload {
  id: string
  property_id: string
  title: string
  tenant: string
  category: string
  priority: MaintenancePriority
  due_at: string
}

export interface MaintenanceAssignPayload {
  assignee: string
}

export type FinanceCreateStatus = 'paid' | 'pending' | 'overdue'
export type FinanceStatus = FinanceCreateStatus | 'reconciled'
export type FinanceLifecycleType = 'rent' | 'renewal' | 'settlement'

export interface FinanceTransactionCreatePayload {
  id: string
  property_id: string
  date: string
  type: string
  tenant: string | null
  amount: number
  method: string
  status: FinanceCreateStatus
  note: string
}

export interface FinanceTransaction {
  id: string
  property_id: string
  date: string
  type: string
  room: string
  tenant: string
  amount: number
  method: string
  status: FinanceStatus
  note: string
  contract_id?: string | null
  settlement_id?: string | null
  lifecycle_type?: FinanceLifecycleType | null
}

export interface RentBillGeneratePayload {
  month: string
}

export interface RentBillGenerateResult {
  month: string
  created: number
  skipped: number
  transactions: FinanceTransaction[]
}

export interface ReconciliationRecordCreatePayload {
  id: string
  date: string
  bank_flow_id: string
  system_flow_id: string
  payer: string
  amount: number
  channel: string
}

export interface ReconciliationImportPayload {
  records: ReconciliationRecordCreatePayload[]
}

export interface ReconciliationRecord extends ReconciliationRecordCreatePayload {
  status: 'matched' | 'pending' | 'exception' | 'reviewed'
  difference: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface PageParams {
  limit?: number
  offset?: number
  q?: string
}

export interface TaskParams extends PageParams {
  source?: TodoSource
  severity?: TodoSeverity
}

export interface AuditLogParams extends PageParams {
  actor_id?: string
  actor_role?: string
  action?: string
  resource_type?: string
  resource_id?: string
  created_from?: string
  created_to?: string
}

export interface AuditLog {
  id: number
  actor_id: string
  actor_name: string
  actor_role: string
  action: string
  resource_type: string
  resource_id: string
  created_at: string
}
