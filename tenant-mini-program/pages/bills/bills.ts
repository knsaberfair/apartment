import { api } from '../../services/api';
import type { BillSummary } from '../../types';

const fallbackBills: BillSummary[] = [
  { id: 'bill-1001', period: '2026-07', amount: 3200, status: 'unpaid', dueDate: '2026-07-31', method: '未支付', type: 'rent' },
  { id: 'bill-1000', period: '2026-06', amount: 3200, status: 'paid', dueDate: '2026-06-30', method: '微信支付', type: 'rent' },
];

Page({
  data: {
    bills: [] as BillSummary[],
    selected: null as BillSummary | null,
    paying: false,
  },
  onShow() {
    this.loadBills();
  },
  async loadBills() {
    try {
      const bills = await api.getBills();
      this.setData({ bills, selected: bills[0] || null });
    } catch {
      this.setData({ bills: fallbackBills, selected: fallbackBills[0] });
    }
  },
  selectBill(e: WechatMiniprogram.BaseEvent) {
    const id = e.currentTarget.dataset.id as string;
    const selected = this.data.bills.find((item) => item.id === id) || null;
    this.setData({ selected });
  },
  async onPay() {
    const bill = this.data.selected;
    if (!bill || bill.status === 'paid') {
      return;
    }

    this.setData({ paying: true });
    try {
      const paidBill = await api.payBill(bill.id);
      const bills = this.data.bills.map((item) => (item.id === paidBill.id ? paidBill : item));
      this.setData({ bills, selected: paidBill });
      wx.showToast({ title: 'Payment successful', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : 'Payment failed', icon: 'none' });
    } finally {
      this.setData({ paying: false });
    }
  },
});
