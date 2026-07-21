import { expect, test } from '@playwright/test'
import { login } from './helpers/auth'

test('viewer cannot see notification center entry', async ({ page }) => {
  await login(page, 'viewer', 'viewer123')

  await expect(page.getByRole('button', { name: /通知提醒/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /权限管理/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /房源管理/ })).toBeVisible()
})

test('viewer is redirected away from unauthorized routes', async ({ page }) => {
  await login(page, 'viewer', 'viewer123')

  await page.goto('/tasks')
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: '管理控制台' })).toBeVisible()
})
