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

async function searchProperty(page: Page, keyword: string) {
  await page.getByLabel('页面搜索').fill(keyword)
  await expect(page.getByRole('row').filter({ hasText: keyword })).toBeVisible()
}

async function deletePropertyByApi(page: Page, propertyId: string) {
  const response = await page.request.delete(`/api/properties/${encodeURIComponent(propertyId)}`)
  expect([200, 204, 404]).toContain(response.status())
}

test('admin can create edit and delete a property', async ({ page }) => {
  const suffix = `${Date.now()}-${test.info().workerIndex}`
  const propertyId = `E2E-${suffix}`
  const updatedBuilding = `E2E 编辑楼 ${suffix}`

  await login(page, 'admin', 'admin123')
  await deletePropertyByApi(page, propertyId)

  try {
    await page.getByTestId('desktop-nav-properties').click()
    await expect(page.getByRole('heading', { name: '房源管理' })).toBeVisible()

    await page.getByRole('button', { name: '新增房源' }).click()
    const createDialog = page.getByRole('dialog').filter({ hasText: '新增房源' })
    await expect(createDialog).toBeVisible()

    await fillTextField(createDialog, '房源编号', propertyId)
    await fillTextField(createDialog, '楼栋', `E2E 楼 ${suffix}`)
    await fillTextField(createDialog, '房号', '1201')
    await fillTextField(createDialog, '户型', '两室一厅')
    await fillNumberField(createDialog, '面积', '88')
    await fillNumberField(createDialog, '月租金', '5200')
    await fillTextField(createDialog, '标签', 'E2E测试，近地铁')
    await createDialog.getByRole('button', { name: '保存房源' }).click()
    await expect(createDialog).toBeHidden()

    await searchProperty(page, propertyId)
    const createdRow = page.getByRole('row').filter({ hasText: propertyId })
    await expect(createdRow).toContainText(`E2E 楼 ${suffix}-1201`)
    await expect(createdRow).toContainText('两室一厅')

    await createdRow.getByRole('button', { name: '编辑' }).click()
    const editDialog = page.getByRole('dialog').filter({ hasText: '编辑房源' })
    await expect(editDialog).toBeVisible()
    await fillTextField(editDialog, '楼栋', updatedBuilding)
    await fillTextField(editDialog, '房号', '1301')
    await fillNumberField(editDialog, '月租金', '5600')
    await fillTextField(editDialog, '标签', 'E2E测试，已编辑')
    await editDialog.getByRole('button', { name: '保存房源' }).click()
    await expect(editDialog).toBeHidden()

    await searchProperty(page, propertyId)
    const updatedRow = page.getByRole('row').filter({ hasText: propertyId })
    await expect(updatedRow).toContainText(`${updatedBuilding}-1301`)
    await expect(updatedRow).toContainText('¥5,600')
    await expect(updatedRow).toContainText('已编辑')

    await updatedRow.getByRole('button', { name: '删除' }).click()
    const confirmDialog = page.getByRole('dialog').filter({ hasText: '删除确认' })
    await expect(confirmDialog).toBeVisible()
    await confirmDialog.getByRole('button', { name: '删除' }).click()

    await expect(page.getByRole('row').filter({ hasText: propertyId })).toBeHidden()
  } finally {
    await deletePropertyByApi(page, propertyId)
  }
})
