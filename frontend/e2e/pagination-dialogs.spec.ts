import { expect, type Page, test } from '@playwright/test'
import { login } from './helpers/auth'

async function navigateTo(page: Page, key: string, heading: string) {
  await page.getByTestId(`desktop-nav-${key}`).click()
  await expect(page.getByRole('heading', { name: heading })).toBeVisible()
}

async function expectPagination(page: Page) {
  await expect(page.locator('.el-pagination')).toBeVisible()
}

async function openAndCloseDialog(page: Page, actionName: string, dialogName: string) {
  await page.getByRole('button', { name: actionName }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: dialogName })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消' }).click()
  await expect(dialog).toBeHidden()
}

test('admin can open and close primary form dialogs', async ({ page }) => {
  await login(page, 'admin', 'admin123')

  await navigateTo(page, 'properties', '房源管理')
  await expectPagination(page)
  await openAndCloseDialog(page, '新增房源', '新增房源')

  await navigateTo(page, 'tenants', '租客列表')
  await expectPagination(page)
  await openAndCloseDialog(page, '新增租客', '新增租客')

  await navigateTo(page, 'maintenance', '工单维修')
  await expectPagination(page)
  await openAndCloseDialog(page, '创建工单', '创建维修工单')

  await navigateTo(page, 'finance', '财务管理')
  await expectPagination(page)
  await openAndCloseDialog(page, '新增账单', '新增账单')

  await navigateTo(page, 'reconciliation', '财务流水对账单')
  await expectPagination(page)
  await openAndCloseDialog(page, '导入流水', '导入流水')
})

test('admin can see pagination on contracts and notification lists', async ({ page }) => {
  await login(page, 'admin', 'admin123')

  await navigateTo(page, 'contracts', '合同管理中心')
  await expectPagination(page)
  await openAndCloseDialog(page, '新建合同', '新建合同')

  await navigateTo(page, 'tasks', '通知提醒中心')
  await expectPagination(page)
  await expect(page.getByTestId('source-filter')).toBeVisible()
  await expect(page.getByTestId('severity-filter')).toBeVisible()
})
