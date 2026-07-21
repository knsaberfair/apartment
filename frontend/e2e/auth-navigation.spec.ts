import { expect, test } from '@playwright/test'
import { login } from './helpers/auth'

test('admin can log in and navigate to notification center', async ({ page }) => {
  await login(page, 'admin', 'admin123')

  await expect(page.getByText('公寓运营系统')).toBeVisible()
  await expect(page.getByRole('button', { name: /房源管理/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /合同管理/ })).toBeVisible()

  await page.getByTestId('desktop-nav-tasks').click()

  await expect(page).toHaveURL(/\/tasks$/)
  await expect(page.getByRole('heading', { name: '通知提醒中心' })).toBeVisible()
  await expect(page.getByText('全部提醒')).toBeVisible()
  await expect(page.getByText('紧急通知')).toBeVisible()
})

test('admin can log in from a direct route and keep the destination', async ({ page }) => {
  await page.goto('/tasks')
  await expect(page).toHaveURL(/\/login\?redirect=\/tasks$/)

  await page.getByTestId('login-username').fill('admin')
  await page.getByTestId('login-password').fill('admin123')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page).toHaveURL(/\/tasks$/)
  await expect(page.getByRole('heading', { name: '通知提醒中心' })).toBeVisible()
})
