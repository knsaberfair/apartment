import { expect, type Page } from '@playwright/test'

export async function login(page: Page, username: string, password: string) {
  await page.goto('/')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '管理控制台' })).toBeVisible()
}
