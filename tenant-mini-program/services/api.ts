import type { ApiError, ApiResponse, BillSummary, ContractSummary, RepairCreateInput, RepairTicket, TenantProfile } from '../types';

type BackendTenantProfile = {
  id: string;
  account_id: string;
  name: string;
  display_name: string;
  phone: string;
  property_id: string;
  room: string;
  contract_id: string;
  payment_status: string;
  move_in_date: string;
  lease_end: string;
  balance: number;
};

type BackendTenantAuthResponse = {
  access_token: string;
  token_type: 'bearer';
  profile: BackendTenantProfile;
};

type BackendTenantContract = {
  id: string;
  property_id: string;
  room: string;
  tenant: string;
  start_date: string;
  end_date: string;
  monthly_rent: number;
  deposit: number;
  status: string;
  days_left: number;
};

type BackendTenantBill = {
  id: string;
  property_id: string;
  room: string;
  tenant: string;
  date: string;
  type: string;
  amount: number;
  method: string;
  status: string;
  note: string;
  contract_id: string | null;
};

type BackendTenantRepair = {
  id: string;
  property_id: string;
  room: string;
  tenant: string;
  title: string;
  category: string;
  priority: string;
  status: string;
  assignee: string;
  created_at: string;
  due_at: string;
};

const request = <T>(url: string, method: WechatMiniprogram.RequestMethod = 'GET', data?: unknown) => {
  const app = getApp<IAppOption>();
  return new Promise<T>((resolve, reject) => {
    wx.request<ApiResponse<T>>({
      url: `${app.globalData.apiBaseUrl}${url}`,
      method,
      data,
      header: app.globalData.token ? { Authorization: `Bearer ${app.globalData.token}` } : undefined,
      success(res) {
        const payload = res.data;
        if (res.statusCode >= 200 && res.statusCode < 300) {
          if (payload && typeof payload === 'object' && 'data' in payload) {
            resolve(payload.data);
            return;
          }
          resolve(payload as unknown as T);
          return;
        }
        let message = (payload && typeof payload === 'object' && 'message' in payload && payload.message) || 'Request failed';
        let code: string | undefined;
        if (payload && typeof payload === 'object' && 'detail' in payload) {
          const detail = (payload as { detail?: ApiError }).detail;
          code = detail?.code;
          message = detail?.message || message;
        }
        const error = new Error(message) as Error & { code?: string };
        error.code = code;
        reject(error);
      },
      fail(err) {
        reject(err);
      },
    });
  });
};

const mapTenantProfile = (profile: BackendTenantProfile): TenantProfile => ({
  id: profile.id,
  name: profile.display_name,
  phone: profile.phone,
  apartment: profile.property_id,
  room: profile.room,
});

const mapContract = (item: BackendTenantContract): ContractSummary => ({
  id: item.id,
  apartment: item.property_id,
  room: item.room,
  status: item.status,
  startDate: item.start_date,
  endDate: item.end_date,
  tenant: item.tenant,
  monthlyRent: item.monthly_rent,
  deposit: item.deposit,
  daysLeft: item.days_left,
});

const mapBill = (item: BackendTenantBill): BillSummary => ({
  id: item.id,
  period: item.date.slice(0, 7),
  amount: item.amount,
  status: item.status,
  dueDate: item.date,
  apartment: item.property_id,
  room: item.room,
  tenant: item.tenant,
  method: item.method,
  note: item.note,
  type: item.type,
  contractId: item.contract_id,
});

const mapRepair = (item: BackendTenantRepair): RepairTicket => ({
  id: item.id,
  title: item.title,
  status: item.status,
  createdAt: item.created_at,
  apartment: item.property_id,
  room: item.room,
  tenant: item.tenant,
  category: item.category,
  priority: item.priority,
  assignee: item.assignee,
  dueAt: item.due_at,
});

const mapAuthResponse = (response: BackendTenantAuthResponse) => ({
  access_token: response.access_token,
  tenant: mapTenantProfile(response.profile),
});

export const api = {
  request,
  async login(code: string) {
    const response = await request<BackendTenantAuthResponse>('/api/tenant/auth/login', 'POST', { code });
    return mapAuthResponse(response);
  },
  async bind(tenantId: string, code: string, displayName: string) {
    const response = await request<BackendTenantAuthResponse>('/api/tenant/auth/bind', 'POST', {
      tenant_id: tenantId,
      code,
      display_name: displayName,
    });
    return mapAuthResponse(response);
  },
  async getProfile() {
    const profile = await request<BackendTenantProfile>('/api/tenant/profile');
    return mapTenantProfile(profile);
  },
  async getContracts() {
    const contracts = await request<BackendTenantContract[]>('/api/tenant/contracts');
    return contracts.map(mapContract);
  },
  async getBills() {
    const bills = await request<BackendTenantBill[]>('/api/tenant/bills');
    return bills.map(mapBill);
  },
  async payBill(billId: string) {
    const bill = await request<BackendTenantBill>(`/api/tenant/bills/${billId}/pay`, 'POST');
    return mapBill(bill);
  },
  async getRepairs() {
    const repairs = await request<BackendTenantRepair[]>('/api/tenant/repairs');
    return repairs.map(mapRepair);
  },
  async createRepair(payload: RepairCreateInput) {
    const repair = await request<BackendTenantRepair>('/api/tenant/repairs', 'POST', {
      title: payload.title,
      category: payload.category,
      priority: payload.priority,
      due_at: payload.dueAt,
    });
    return mapRepair(repair);
  },
};
