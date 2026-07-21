export type TenantProfile = {
  id: string;
  name: string;
  phone: string;
  apartment?: string;
  room?: string;
};

export type ContractSummary = {
  id: string;
  apartment: string;
  room: string;
  status: string;
  startDate: string;
  endDate: string;
  tenant?: string;
  monthlyRent?: number;
  deposit?: number;
  daysLeft?: number;
};

export type BillSummary = {
  id: string;
  period: string;
  amount: number;
  status: 'unpaid' | 'paid' | 'overdue' | string;
  dueDate: string;
  apartment?: string;
  room?: string;
  tenant?: string;
  method?: string;
  note?: string;
  type?: string;
  contractId?: string | null;
};

export type RepairTicket = {
  id: string;
  title: string;
  status: string;
  createdAt: string;
  apartment?: string;
  room?: string;
  tenant?: string;
  category?: string;
  priority?: string;
  assignee?: string;
  dueAt?: string;
};

export type RepairCreateInput = {
  title: string;
  category: string;
  priority: string;
  dueAt: string;
};

export type ApiResponse<T> = {
  code?: number;
  message?: string;
  data: T;
};

export type ApiError = {
  code?: string;
  message?: string;
};
