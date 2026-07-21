import type { TenantProfile } from '../../types';

Page({
  data: {
    tenant: null as TenantProfile | null,
  },
  onShow() {
    const tenant = getApp<IAppOption>().globalData.tenant || wx.getStorageSync('tenant');
    this.setData({ tenant });
  },
  onLogout() {
    getApp<IAppOption>().clearTenant();
    wx.reLaunch({ url: '/pages/login/login' });
  },
});
