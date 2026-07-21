import { api } from '../../services/api';
import type { BillSummary, ContractSummary, RepairTicket, TenantProfile } from '../../types';

const fallbackBills: BillSummary[] = [
  { id: 'bill-1001', period: '2026-07', amount: 3200, status: 'unpaid', dueDate: '2026-07-31' },
  { id: 'bill-1000', period: '2026-06', amount: 3200, status: 'paid', dueDate: '2026-06-30' },
];

Page({
  data: {
    tenant: null as TenantProfile | null,
    contracts: [] as ContractSummary[],
    bills: [] as BillSummary[],
    repairs: [] as RepairTicket[],
  },
  onShow() {
    const app = getApp<IAppOption>();
    const tenant = app.globalData.tenant || wx.getStorageSync('tenant');
    if (!tenant) {
      wx.reLaunch({ url: '/pages/login/login' });
      return;
    }

    this.setData({ tenant });
    this.loadData();
  },
  loadData() {
    void this.loadContracts();
    void this.loadBills();
    void this.loadRepairs();
  },
  async loadContracts() {
    try {
      const contracts = await api.getContracts();
      this.setData({ contracts });
    } catch {
      this.setData({
        contracts: [
          { id: 'ctr-2026-01', apartment: 'Sunrise Gardens', room: 'B-1204', status: 'active', startDate: '2026-01-01', endDate: '2026-12-31' },
        ],
      });
    }
  },
  async loadBills() {
    try {
      const bills = await api.getBills();
      this.setData({ bills });
    } catch {
      this.setData({ bills: fallbackBills });
    }
  },
  async loadRepairs() {
    try {
      const repairs = await api.getRepairs();
      this.setData({ repairs });
    } catch {
      this.setData({
        repairs: [
          { id: 'rep-8801', title: 'Air conditioner filter cleaning', status: 'in progress', createdAt: '2026-07-18' },
          { id: 'rep-8800', title: 'Kitchen faucet drip', status: 'submitted', createdAt: '2026-07-12' },
        ],
      });
    }
  },
  goTo(e: WechatMiniprogram.BaseEvent) {
    const page = e.currentTarget.dataset.page as string;
    wx.navigateTo({ url: `/pages/${page}/${page}` });
  },
});
