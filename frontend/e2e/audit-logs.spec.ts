import { expect, test } from '@playwright/test'
import { login } from './helpers/auth'

test('admin can view paginated audit logs and filters', async ({ page }) => {
  await login(page, 'admin', 'admin123')

  await page.getByTestId('desktop-nav-auditLogs').click()
  await expect(page.getByRole('heading', { name: '操作审计' })).toBeVisible()
  await expect(page.locator('.el-pagination')).toBeVisible()
  await expect(page.getByTestId('audit-action-filter')).toBeVisible()
  await expect(page.getByTestId('audit-resource-filter')).toBeVisible()
  await expect(page.getByTestId('audit-role-filter')).toBeVisible()
  await expect(page.getByText('匹配日志总数')).toBeVisible()

  await page.getByLabel('页面搜索').fill('property')
  await expect(page.locator('.el-alert')).toBeHidden()
})
