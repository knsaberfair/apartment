import { api } from '../../services/api';
import type { TenantProfile } from '../../types';

const getWxLoginCode = (tenantId: string) => {
  const app = getApp<IAppOption>();
  if (app.globalData.apiBaseUrl.includes('127.0.0.1') || app.globalData.apiBaseUrl.includes('localhost')) {
    return Promise.resolve(`tenant-dev-${tenantId}`);
  }

  return new Promise<string>((resolve, reject) => {
    wx.login({
      success(result) {
        if (result.code) {
          resolve(result.code);
          return;
        }
        reject(new Error('Failed to get WeChat login code.'));
      },
      fail(err) {
        reject(err);
      },
    });
  });
};

Page({
  data: {
    tenantId: '',
    loading: false,
    error: '',
  },
  onTenantInput(e: WechatMiniprogram.Input) {
    this.setData({ tenantId: e.detail.value });
  },
  async onLogin() {
    const tenantId = this.data.tenantId.trim();
    if (!tenantId) {
      this.setData({ error: 'Please enter a tenant ID.' });
      return;
    }

    this.setData({ loading: true, error: '' });
    try {
      const code = await getWxLoginCode(tenantId);
      let result;
      try {
        result = await api.login(code);
      } catch (error) {
        if (!(error instanceof Error) || (error as Error & { code?: string }).code !== 'TENANT_NOT_BOUND') {
          throw error;
        }
        result = await api.bind(tenantId, code, tenantId);
      }
      const tenant: TenantProfile = result.tenant;
      const app = getApp<IAppOption>();
      app.globalData.token = result.access_token;
      wx.setStorageSync('token', result.access_token);
      app.setTenant(tenant);
      wx.reLaunch({ url: '/pages/home/home' });
    } catch (error) {
      this.setData({ error: error instanceof Error ? error.message : 'Login failed.' });
    } finally {
      this.setData({ loading: false });
    }
  },
});
