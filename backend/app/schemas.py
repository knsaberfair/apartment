from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


TodoSeverity = Literal["info", "warning", "danger"]
TodoSource = Literal["contracts", "maintenance", "finance", "reconciliation"]


class TodoItem(BaseModel):
    id: str
    source: TodoSource
    source_id: str
    title: str
    description: str
    due_date: str | None = None
    severity: TodoSeverity
    status: str
    assignee: str | None = None
    related_room: str | None = None
    related_person: str | None = None


class TodoSummary(BaseModel):
    total: int
    urgent: int
    overdue: int
    items: list[TodoItem]
    limit: int | None = None
    offset: int | None = None


PropertyStatus = Literal["occupied", "vacant", "reserved", "maintenance"]


class PropertyBase(BaseModel):
    building: str
    room: str
    layout: str
    area: float = Field(gt=0)
    rent: int = Field(ge=0)
    status: PropertyStatus
    tenant: str | None = None
    lease_end: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("building", "room", "layout", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("tenant", "lease_end", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tags must be a list")
        return [tag.strip() for tag in value if isinstance(tag, str) and tag.strip()]

    @model_validator(mode="after")
    def validate_status_details(self):
        if self.status == "vacant" and (self.tenant or self.lease_end):
            raise ValueError("vacant property cannot have tenant or lease_end")
        if self.status in {"occupied", "reserved"} and (not self.tenant or not self.lease_end):
            raise ValueError("occupied or reserved property requires tenant and lease_end")
        return self


class PropertyCreate(PropertyBase):
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class PropertyUpdate(PropertyBase):
    pass


class Property(PropertyCreate):
    pass


class PropertyOption(BaseModel):
    id: str
    building: str
    room: str


class PropertyPage(BaseModel):
    items: list[Property]
    total: int
    limit: int
    offset: int


PaymentStatus = Literal["paid", "pending", "overdue", "reconciled"]
TenantStatus = Literal["active", "moved_out"]
LifecycleType = Literal["rent", "renewal", "settlement"]


class TenantBase(BaseModel):
    property_id: str
    name: str
    phone: str
    contract_id: str
    payment_status: PaymentStatus
    move_in_date: str
    lease_end: str
    balance: int = Field(ge=0)
    status: TenantStatus = "active"
    move_out_date: str | None = None

    @field_validator("property_id", "name", "phone", "contract_id", "move_in_date", "lease_end", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("move_in_date", "lease_end", "move_out_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value

    @model_validator(mode="after")
    def validate_lease_dates(self):
        if date.fromisoformat(self.lease_end) < date.fromisoformat(self.move_in_date):
            raise ValueError("lease_end must be greater than or equal to move_in_date")
        if self.status == "active" and self.move_out_date is not None:
            raise ValueError("active tenant cannot have move_out_date")
        if self.status == "moved_out" and self.move_out_date is None:
            raise ValueError("moved_out tenant requires move_out_date")
        if self.move_out_date is not None and date.fromisoformat(self.move_out_date) < date.fromisoformat(self.move_in_date):
            raise ValueError("move_out_date must be greater than or equal to move_in_date")
        return self


class TenantCreate(TenantBase):
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class TenantUpdate(TenantBase):
    pass


class Tenant(TenantCreate):
    room: str


class TenantPage(BaseModel):
    items: list[Tenant]
    total: int
    limit: int
    offset: int


class TenantAuthBindRequest(BaseModel):
    tenant_id: str
    code: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=60)
    unionid: str | None = Field(default=None, max_length=128)

    @field_validator("tenant_id", "code", "display_name", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class TenantAuthLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)


class TenantProfile(BaseModel):
    id: str
    account_id: str
    name: str
    display_name: str
    phone: str
    property_id: str
    room: str
    contract_id: str
    payment_status: PaymentStatus
    move_in_date: str
    lease_end: str
    balance: int


class TenantContract(BaseModel):
    id: str
    property_id: str
    room: str
    tenant: str
    start_date: str
    end_date: str
    monthly_rent: int
    deposit: int
    status: str
    days_left: int


class TenantBill(BaseModel):
    id: str
    property_id: str
    room: str
    tenant: str
    date: str
    type: str
    amount: int
    method: str
    status: str
    note: str
    contract_id: str | None = None


class TenantRepair(BaseModel):
    id: str
    property_id: str
    room: str
    tenant: str
    title: str
    category: str
    priority: str
    status: str
    assignee: str
    created_at: str
    due_at: str


MaintenancePriority = Literal["low", "medium", "high", "urgent"]


class TenantRepairCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    priority: MaintenancePriority
    due_at: str

    @field_validator("title", "category", "due_at", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value


class TenantHome(BaseModel):
    profile: TenantProfile
    contract_count: int
    bill_count: int
    repair_count: int
    recent_contracts: list[TenantContract]
    recent_bills: list[TenantBill]
    recent_repairs: list[TenantRepair]


class TenantAuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    profile: TenantProfile


ContractStatus = Literal["active", "pending", "expiring", "terminated"]


class ContractBase(BaseModel):
    property_id: str
    tenant: str
    start_date: str
    end_date: str
    monthly_rent: int = Field(ge=0)
    deposit: int = Field(ge=0)

    @field_validator("property_id", "tenant", "start_date", "end_date", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value

    @model_validator(mode="after")
    def validate_contract_dates(self):
        if date.fromisoformat(self.end_date) < date.fromisoformat(self.start_date):
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class ContractCreate(ContractBase):
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class ContractUpdatePending(ContractBase):
    pass


class Contract(ContractCreate):
    room: str
    status: ContractStatus
    days_left: int


class ContractPage(BaseModel):
    items: list[Contract]
    total: int
    limit: int
    offset: int


MaintenanceStatus = Literal["open", "in_progress", "resolved"]


class MaintenanceOrderCreate(BaseModel):
    id: str = Field(max_length=40)
    property_id: str
    title: str = Field(max_length=120)
    tenant: str = Field(max_length=60)
    category: str = Field(max_length=40)
    priority: MaintenancePriority
    due_at: str

    @field_validator("id", "property_id", "title", "tenant", "category", "due_at", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("due_at")
    @classmethod
    def validate_due_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value


class MaintenanceAssignRequest(BaseModel):
    assignee: str = Field(max_length=60)

    @field_validator("assignee", mode="before")
    @classmethod
    def normalize_assignee(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()


class MaintenanceOrder(MaintenanceOrderCreate):
    room: str
    status: MaintenanceStatus
    assignee: str
    created_at: str


class MaintenanceOrderPage(BaseModel):
    items: list[MaintenanceOrder]
    total: int
    limit: int
    offset: int


FinanceCreateStatus = Literal["paid", "pending", "overdue"]
FinanceStatus = Literal["paid", "pending", "overdue", "reconciled"]
ReconciliationStatus = Literal["matched", "pending", "exception", "reviewed"]


class FinanceTransactionCreate(BaseModel):
    id: str = Field(max_length=40)
    property_id: str
    date: str
    type: str = Field(max_length=40)
    tenant: str | None = Field(default=None, max_length=60)
    amount: int
    method: str = Field(max_length=40)
    status: FinanceCreateStatus
    note: str = Field(default="", max_length=120)
    contract_id: str | None = None
    settlement_id: str | None = None
    lifecycle_type: LifecycleType | None = None

    @field_validator("id", "property_id", "date", "type", "method", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("tenant", "note", "contract_id", "settlement_id", "lifecycle_type", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("field must be text")
        return value.strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must be non-zero")
        return value

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value


class FinanceTransaction(FinanceTransactionCreate):
    property_id: str
    room: str
    tenant: str
    status: FinanceStatus
    note: str


class FinanceTransactionPage(BaseModel):
    items: list[FinanceTransaction]
    total: int
    limit: int
    offset: int


class ContractRenewalRequest(BaseModel):
    new_end_date: str
    monthly_rent: int = Field(ge=0)
    deposit: int = Field(ge=0)

    @field_validator("new_end_date")
    @classmethod
    def validate_new_end_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value


class ContractRenewal(BaseModel):
    id: str
    contract_id: str
    property_id: str
    tenant: str
    room: str
    old_end_date: str
    new_end_date: str
    monthly_rent: int
    deposit: int
    created_at: str


class MoveOutRequest(BaseModel):
    move_out_date: str
    reason: str = Field(default="", max_length=120)

    @field_validator("move_out_date")
    @classmethod
    def validate_move_out_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("field must be text")
        return value.strip()


class MoveOut(BaseModel):
    id: str
    contract_id: str
    property_id: str
    tenant: str
    room: str
    move_out_date: str
    reason: str
    status: str
    created_at: str


class DepositSettlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deductions: int | None = Field(default=None, ge=0)
    rent_deduction: int = Field(default=0, ge=0)
    utility_deduction: int = Field(default=0, ge=0)
    damage_deduction: int = Field(default=0, ge=0)
    cleaning_deduction: int = Field(default=0, ge=0)
    other_deduction: int = Field(default=0, ge=0)
    settled_date: str
    method: str = Field(default="银行转账", max_length=40)
    note: str = Field(default="退租押金结算", max_length=120)

    @field_validator("method", "note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            return value
        return value.strip()

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        if not value:
            raise ValueError("method is required")
        return value

    @field_validator("settled_date")
    @classmethod
    def validate_settled_date(cls, value: str) -> str:
        parts = value.split("-")
        if len(parts) != 3 or len(parts[0]) != 4 or len(parts[1]) != 2 or len(parts[2]) != 2:
            raise ValueError("date must use YYYY-MM-DD format")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value

    @model_validator(mode="after")
    def normalize_deductions(self):
        detailed_total = self.rent_deduction + self.utility_deduction + self.damage_deduction + self.cleaning_deduction + self.other_deduction
        if self.deductions is None:
            self.deductions = detailed_total
        elif detailed_total == 0 and self.deductions > 0:
            self.other_deduction = self.deductions
        elif self.deductions != detailed_total:
            raise ValueError("deductions must equal detailed deduction total")
        return self


class DepositSettlement(BaseModel):
    id: str
    move_out_id: str
    contract_id: str
    property_id: str
    tenant: str
    room: str
    deposit: int
    deductions: int
    rent_deduction: int = 0
    utility_deduction: int = 0
    damage_deduction: int = 0
    cleaning_deduction: int = 0
    other_deduction: int = 0
    refund_amount: int
    settled_date: str
    status: str
    method: str = "银行转账"
    note: str = "退租押金结算"
    finance_transaction_id: str | None = None


class RentBillGenerateRequest(BaseModel):
    month: str

    @field_validator("month", mode="before")
    @classmethod
    def validate_month(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("month is required")
        normalized = value.strip()
        parts = normalized.split("-")
        if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
            raise ValueError("month must use YYYY-MM format")
        try:
            date(int(parts[0]), int(parts[1]), 1)
        except ValueError as exc:
            raise ValueError("month must be a valid month") from exc
        return normalized


class RentBillGenerateResult(BaseModel):
    month: str
    created: int
    skipped: int
    transactions: list[FinanceTransaction]


class ReconciliationRecordCreate(BaseModel):
    id: str = Field(max_length=40)
    date: str
    bank_flow_id: str = Field(max_length=60)
    system_flow_id: str = Field(max_length=60)
    payer: str = Field(max_length=60)
    amount: int
    channel: str = Field(max_length=40)

    @field_validator("id", "date", "bank_flow_id", "system_flow_id", "payer", "channel", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field is required")
        return value.strip()

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date") from exc
        return value

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must be non-zero")
        return value


class ReconciliationImportRequest(BaseModel):
    records: list[ReconciliationRecordCreate] = Field(min_length=1, max_length=100)


class ReconciliationRecord(ReconciliationRecordCreate):
    status: ReconciliationStatus
    difference: int


class ReconciliationRecordPage(BaseModel):
    items: list[ReconciliationRecord]
    total: int
    limit: int
    offset: int


class AuditLog(BaseModel):
    id: int
    actor_id: str
    actor_name: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    created_at: str


class AuditLogPage(BaseModel):
    items: list[AuditLog]
    total: int
    limit: int
    offset: int
