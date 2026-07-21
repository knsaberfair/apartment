import { api } from '../../services/api';
import type { ContractSummary } from '../../types';

Page({
  data: {
    contracts: [] as ContractSummary[],
    selected: null as ContractSummary | null,
  },
  onShow() {
    this.loadContracts();
  },
  async loadContracts() {
    try {
      const contracts = await api.getContracts();
      this.setData({ contracts, selected: contracts[0] || null });
    } catch {
      const contracts: ContractSummary[] = [
        { id: 'ctr-2026-01', apartment: 'Sunrise Gardens', room: 'B-1204', status: 'active', startDate: '2026-01-01', endDate: '2026-12-31', monthlyRent: 3200, deposit: 3200, daysLeft: 180 },
      ];
      this.setData({ contracts, selected: contracts[0] });
    }
  },
  selectContract(e: WechatMiniprogram.BaseEvent) {
    const id = e.currentTarget.dataset.id as string;
    const selected = this.data.contracts.find((item) => item.id === id) || null;
    this.setData({ selected });
  },
});
