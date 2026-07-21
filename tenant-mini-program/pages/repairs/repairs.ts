import { api } from '../../services/api';
import type { RepairTicket } from '../../types';

const todayPlusSevenDays = () => {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toISOString().slice(0, 10);
};

Page({
  data: {
    repairs: [] as RepairTicket[],
    selected: null as RepairTicket | null,
    priorities: ['low', 'medium', 'high', 'urgent'],
    form: {
      title: '',
      category: '家电',
      priority: 'medium',
      dueAt: todayPlusSevenDays(),
    },
    submitting: false,
  },
  onShow() {
    this.loadRepairs();
  },
  async loadRepairs() {
    try {
      const repairs = await api.getRepairs();
      this.setData({ repairs, selected: repairs[0] || null });
    } catch {
      const repairs: RepairTicket[] = [
        { id: 'rep-8801', title: 'Air conditioner filter cleaning', status: 'in progress', createdAt: '2026-07-18', category: '家电', priority: 'medium', assignee: '物业工程' },
        { id: 'rep-8800', title: 'Kitchen faucet drip', status: 'submitted', createdAt: '2026-07-12', category: '水电', priority: 'low', assignee: '未分配' },
      ];
      this.setData({ repairs, selected: repairs[0] });
    }
  },
  selectRepair(e: WechatMiniprogram.BaseEvent) {
    const id = e.currentTarget.dataset.id as string;
    const selected = this.data.repairs.find((item) => item.id === id) || null;
    this.setData({ selected });
  },
  onTitleInput(e: WechatMiniprogram.Input) {
    this.setData({ 'form.title': e.detail.value });
  },
  onCategoryInput(e: WechatMiniprogram.Input) {
    this.setData({ 'form.category': e.detail.value });
  },
  onPriorityChange(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.priority': this.data.priorities[Number(e.detail.value)] });
  },
  onDueDateChange(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.dueAt': e.detail.value });
  },
  async onSubmitRepair() {
    const form = this.data.form;
    if (!form.title.trim() || !form.category.trim()) {
      wx.showToast({ title: 'Please fill title and category', icon: 'none' });
      return;
    }

    this.setData({ submitting: true });
    try {
      const repair = await api.createRepair({
        title: form.title.trim(),
        category: form.category.trim(),
        priority: form.priority,
        dueAt: form.dueAt,
      });
      this.setData({
        repairs: [repair, ...this.data.repairs],
        selected: repair,
        form: { title: '', category: '家电', priority: 'medium', dueAt: todayPlusSevenDays() },
      });
      wx.showToast({ title: 'Repair submitted', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : 'Submit failed', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },
});
