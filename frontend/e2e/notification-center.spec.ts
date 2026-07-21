import { expect, test } from '@playwright/test'
import { login } from './helpers/auth'

test('notification center renders summary cards and filters', async ({ page }) => {
  await login(page, 'admin', 'admin123')
  await page.getByTestId('desktop-nav-tasks').click()

  await expect(page.getByRole('heading', { name: '通知提醒中心' })).toBeVisible()
  await expect(page.getByText('全部提醒')).toBeVisible()
  await expect(page.getByText('紧急提醒')).toBeVisible()
  await expect(page.getByText('已逾期')).toBeVisible()
  await expect(page.getByText('今日到期')).toBeVisible()
  await expect(page.getByText('7 日内到期')).toBeVisible()

  await page.getByRole('button', { name: /刷新提醒/ }).click()
  await expect(page.getByText('全部提醒')).toBeVisible()

  await page.getByTestId('source-filter').click()
  await page.getByRole('option', { name: '合同' }).click()
  await expect(page.getByText('全部提醒')).toBeVisible()

  await page.getByTestId('severity-filter').click()
  await page.getByRole('option', { name: '紧急' }).click()
  await expect(page.getByText(/项$/)).toBeVisible()
})
