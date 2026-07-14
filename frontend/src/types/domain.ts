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

export interface Property {
  id: string
  building: string
  room: string
  layout: string
  area: number
  rent: number
  status: 'occupied' | 'vacant' | 'reserved' | 'maintenance'
  tenant: string | null
  lease_end: string | null
  tags: string[]
}

export interface Tenant {
  id: string
  name: string
  phone: string
  room: string
  contract_id: string
  payment_status: 'paid' | 'pending' | 'overdue' | 'reconciled'
  move_in_date: string
  lease_end: string
  balance: number
}

export interface Contract {
  id: string
  tenant: string
  room: string
  start_date: string
  end_date: string
  monthly_rent: number
  deposit: number
  status: 'active' | 'expiring' | 'pending' | 'terminated'
  days_left: number
}

export interface MaintenanceOrder {
  id: string
  title: string
  room: string
  tenant: string
  category: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: 'open' | 'in_progress' | 'waiting' | 'resolved'
  assignee: string
  created_at: string
  due_at: string
}

export interface FinanceTransaction {
  id: string
  date: string
  type: string
  room: string
  tenant: string
  amount: number
  method: string
  status: 'paid' | 'pending' | 'overdue' | 'reconciled'
  note: string
}

export interface ReconciliationRecord {
  id: string
  date: string
  bank_flow_id: string
  system_flow_id: string
  payer: string
  amount: number
  channel: string
  status: 'matched' | 'pending' | 'exception'
  difference: number
}
