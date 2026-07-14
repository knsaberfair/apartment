from pydantic import BaseModel


class MetricCard(BaseModel):
    label: str
    value: str
    change: str
    tone: str


class DashboardSummary(BaseModel):
    metrics: list[MetricCard]
    occupancy_rate: int
    monthly_income: int
    pending_tasks: int
    expiring_contracts: int
    recent_contracts: list[dict]
    urgent_work_orders: list[dict]
    income_trend: list[dict]


class Property(BaseModel):
    id: str
    building: str
    room: str
    layout: str
    area: float
    rent: int
    status: str
    tenant: str | None = None
    lease_end: str | None = None
    tags: list[str]


class Tenant(BaseModel):
    id: str
    name: str
    phone: str
    room: str
    contract_id: str
    payment_status: str
    move_in_date: str
    lease_end: str
    balance: int


class Contract(BaseModel):
    id: str
    tenant: str
    room: str
    start_date: str
    end_date: str
    monthly_rent: int
    deposit: int
    status: str
    days_left: int


class MaintenanceOrder(BaseModel):
    id: str
    title: str
    room: str
    tenant: str
    category: str
    priority: str
    status: str
    assignee: str
    created_at: str
    due_at: str


class FinanceTransaction(BaseModel):
    id: str
    date: str
    type: str
    room: str
    tenant: str
    amount: int
    method: str
    status: str
    note: str


class ReconciliationRecord(BaseModel):
    id: str
    date: str
    bank_flow_id: str
    system_flow_id: str
    payer: str
    amount: int
    channel: str
    status: str
    difference: int
