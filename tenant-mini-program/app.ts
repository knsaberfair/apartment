const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

App<IAppOption>({
  globalData: {
    apiBaseUrl: DEFAULT_API_BASE_URL,
    token: '',
    tenant: null,
  },
  onLaunch() {
    const tenant = wx.getStorageSync('tenant');
    const token = wx.getStorageSync('token');
    if (tenant) {
      this.globalData.tenant = tenant;
    }
    if (token) {
      this.globalData.token = token;
    }
  },
  setTenant(tenant) {
    this.globalData.tenant = tenant;
    wx.setStorageSync('tenant', tenant);
  },
  clearTenant() {
    this.globalData.tenant = null;
    this.globalData.token = '';
    wx.setStorageSync('tenant', null);
    wx.setStorageSync('token', '');
  },
});

export {};

declare global {
  interface IAppOption {
    globalData: {
      apiBaseUrl: string;
      token: string;
      tenant: import('./types').TenantProfile | null;
    };
    setTenant(tenant: import('./types').TenantProfile): void;
    clearTenant(): void;
  }
}
