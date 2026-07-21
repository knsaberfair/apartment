import { expect, type Locator, type Page, test } from '@playwright/test'
import { login } from './helpers/auth'

function formItem(dialog: Locator, label: string) {
  return dialog.locator('.el-form-item').filter({ hasText: label })
}

async function fillTextField(dialog: Locator, label: string, value: string) {
  await formItem(dialog, label).getByRole('textbox').fill(value)
}

async function fillNumberField(dialog: Locator, label: string, value: string) {
  await formItem(dialog, label).getByRole('spinbutton').fill(value)
}

async function fillDateField(dialog: Locator, label: string, value: string) {
  await formItem(dialog, label).getByRole('combobox').fill(value)
}

async function selectProperty(dialog: Locator, propertyId: string) {
  await formItem(dialog, '关联房源').locator('.el-select').click()
  await dialog.page().getByRole('option').filter({ hasText: propertyId }).click()
}

async function searchTenant(page: Page, keyword: string) {
  await page.getByLabel('页面搜索').fill(keyword)
  await expect(page.getByRole('row').filter({ hasText: keyword })).toBeVisible()
}

async function deleteTenantByApi(page: Page, tenantId: string) {
  const response = await page.request.delete(`/api/tenants/${encodeURIComponent(tenantId)}`)
  expect([200, 204, 404]).toContain(response.status())
}

async function createPropertyByApi(page: Page, propertyId: string, suffix: string) {
  const response = await page.request.post('/api/properties', {
    data: {
      id: propertyId,
      building: `E2E租客楼${suffix}`,
      room: '1501',
      layout: '一室一厅',
      area: 66,
      rent: 4300,
      status: 'vacant',
      tenant: null,
      lease_end: null,
      tags: ['E2E租客测试'],
    },
  })
  expect([200, 201]).toContain(response.status())
}

async function deletePropertyByApi(page: Page, propertyId: string) {
  const response = await page.request.delete(`/api/properties/${encodeURIComponent(propertyId)}`)
  expect([200, 204, 404]).toContain(response.status())
}

test('admin can create edit and delete a tenant', async ({ page, request }) => {
  const suffix = `${Date.now()}-${test.info().workerIndex}`
  const propertyId = `E2E-T-P-${suffix}`
  const tenantId = `E2E-T-${suffix}`
  const tenantName = `E2E租客${suffix}`
  const updatedName = `E2E租客编辑${suffix}`
  const contractId = `E2E-C-${suffix}`

  await login(page, 'admin', 'admin123')

  await deleteTenantByApi(page, tenantId)
  await deletePropertyByApi(page, propertyId)
  await createPropertyByApi(page, propertyId, suffix)

  try {
    await page.getByTestId('desktop-nav-tenants').click()
    await expect(page.getByRole('heading', { name: '租客列表' })).toBeVisible()

    await page.getByRole('button', { name: '新增租客' }).click()
    const createDialog = page.getByRole('dialog').filter({ hasText: '新增租客' })
    await expect(createDialog).toBeVisible()

    await fillTextField(createDialog, '租客编号', tenantId)
    await selectProperty(createDialog, propertyId)
    await fillTextField(createDialog, '租客姓名', tenantName)
    await fillTextField(createDialog, '联系方式', '13900001111')
    await fillTextField(createDialog, '合同编号', contractId)
    await fillDateField(createDialog, '入住日期', '2026-01-01')
    await fillDateField(createDialog, '租约结束日', '2026-12-31')
    await fillNumberField(createDialog, '当前余额', '1200')
    await createDialog.getByRole('button', { name: '保存租客' }).click()
    await expect(createDialog).toBeHidden()

    await searchTenant(page, tenantId)
    const createdRow = page.getByRole('row').filter({ hasText: tenantId })
    await expect(createdRow).toContainText(tenantName)
    await expect(createdRow).toContainText('13900001111')
    await expect(createdRow).toContainText(contractId)
    await expect(createdRow).toContainText('¥1,200')

    await createdRow.getByRole('button', { name: '编辑' }).click()
    const editDialog = page.getByRole('dialog').filter({ hasText: '编辑租客' })
    await expect(editDialog).toBeVisible()
    await fillTextField(editDialog, '租客姓名', updatedName)
    await fillTextField(editDialog, '联系方式', '13900002222')
    await fillTextField(editDialog, '合同编号', `${contractId}-EDIT`)
    await fillNumberField(editDialog, '当前余额', '0')
    await editDialog.getByRole('button', { name: '保存租客' }).click()
    await expect(editDialog).toBeHidden()

    await searchTenant(page, tenantId)
    const updatedRow = page.getByRole('row').filter({ hasText: tenantId })
    await expect(updatedRow).toContainText(updatedName)
    await expect(updatedRow).toContainText('13900002222')
    await expect(updatedRow).toContainText(`${contractId}-EDIT`)
    await expect(updatedRow).toContainText('¥0')

    await updatedRow.getByRole('button', { name: '删除' }).click()
    const confirmDialog = page.getByRole('dialog').filter({ hasText: '删除确认' })
    await expect(confirmDialog).toBeVisible()
    await confirmDialog.getByRole('button', { name: '删除' }).click()

    await expect(page.getByRole('row').filter({ hasText: tenantId })).toBeHidden()
  } finally {
    await deleteTenantByApi(page, tenantId)
    await deletePropertyByApi(page, propertyId)
  }
})
