<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElMessageBox, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { pageActionPermissions } from '@/config/permissions'
import { ApiError, api, currency } from '@/services/api'
import type { PaymentStatus, Property, Tenant, TenantCreatePayload, TenantUpdatePayload } from '@/types/domain'

interface TenantForm {
  id: string
  property_id: string
  name: string
  phone: string
  contract_id: string
  payment_status: PaymentStatus
  move_in_date: string | null
  lease_end: string | null
  balance: number | null
}

const emptyForm = (): TenantForm => ({
  id: '',
  property_id: '',
  name: '',
  phone: '',
  contract_id: '',
  payment_status: 'pending',
  move_in_date: '',
  lease_end: '',
  balance: 0,
})

const paymentStatusOptions: Array<{ label: string; value: PaymentStatus }> = [
  { label: '已支付', value: 'paid' },
  { label: '待支付', value: 'pending' },
  { label: '逾期', value: 'overdue' },
  { label: '已对账', value: 'reconciled' },
]

const { hasPermission } = usePermissions()
const tenants = ref<Tenant[]>([])
const properties = ref<Property[]>([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref<string | null>(null)
const showForm = ref(false)
const editingTenant = ref<Tenant | null>(null)
const form = ref<TenantForm>(emptyForm())
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let tenantsRequestId = 0

const canCreate = computed(() => hasPermission(pageActionPermissions.tenantCreate))
const canUpdate = computed(() => hasPermission(pageActionPermissions.tenantUpdate))
const canDelete = computed(() => hasPermission(pageActionPermissions.tenantDelete))
const hasActions = computed(() => canUpdate.value || canDelete.value)
const selectableProperties = computed(() => properties.value.filter((property) => property.status === 'vacant' || property.id === editingTenant.value?.property_id))
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedTenants = computed(() => tenants.value)

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => detailMessage(item)).find((message): message is string => !!message) ?? null
  if (!detail || typeof detail !== 'object') return null
  if ('message' in detail && typeof detail.message === 'string') return detail.message
  if ('msg' in detail && typeof detail.msg === 'string') return detail.msg
  if ('detail' in detail) return detailMessage(detail.detail)
  return null
}

function errorMessage(err: unknown, fallback: string) {
  if (err instanceof ApiError) {
    return detailMessage(err.detail) ?? err.message
  }
  return err instanceof Error ? err.message : fallback
}

function validateForm() {
  if (!editingTenant.value && !form.value.id.trim()) return '请输入租客编号'
  if (!form.value.property_id) return '请选择房源'
  if (!form.value.name.trim()) return '请输入租客姓名'
  if (!form.value.phone.trim()) return '请输入联系方式'
  if (!form.value.contract_id.trim()) return '请输入合同编号'
  if (!form.value.move_in_date) return '请选择入住日期'
  if (!form.value.lease_end) return '请选择租约结束日'
  if (form.value.lease_end < form.value.move_in_date) return '租约结束日不能早于入住日期'
  if (form.value.balance === null || form.value.balance === undefined || !Number.isFinite(form.value.balance) || form.value.balance < 0 || !Number.isInteger(form.value.balance)) return '当前余额必须是非负整数'
  return ''
}

function buildUpdatePayload(): TenantUpdatePayload {
  return {
    property_id: form.value.property_id,
    name: form.value.name.trim(),
    phone: form.value.phone.trim(),
    contract_id: form.value.contract_id.trim(),
    payment_status: form.value.payment_status,
    move_in_date: form.value.move_in_date ?? '',
    lease_end: form.value.lease_end ?? '',
    balance: Number(form.value.balance),
  }
}

function buildCreatePayload(): TenantCreatePayload {
  return {
    id: form.value.id.trim(),
    ...buildUpdatePayload(),
  }
}

async function loadTenants() {
  const requestId = ++tenantsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.tenants({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== tenantsRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    tenants.value = response.items
    normalizeCurrentPage()
    return true
  } catch (err) {
    if (requestId === tenantsRequestId) {
      loadError.value = errorMessage(err, '租客加载失败')
    }
    return false
  } finally {
    if (requestId === tenantsRequestId) {
      loading.value = false
    }
  }
}

async function loadProperties() {
  try {
    properties.value = await api.tenantPropertyOptions()
    return true
  } catch (err) {
    actionError.value = errorMessage(err, '房源选项加载失败')
    return false
  }
}

async function ensurePropertiesLoaded() {
  if (properties.value.length) return true
  return loadProperties()
}

async function openCreateForm() {
  if (!canCreate.value) return
  actionError.value = ''
  editingTenant.value = null
  if (!(await ensurePropertiesLoaded())) return
  form.value = emptyForm()
  showForm.value = true
}

function asTenant(row: unknown): Tenant {
  return row as Tenant
}

async function openEditForm(tenant: Tenant) {
  if (!canUpdate.value) return
  actionError.value = ''
  if (!(await ensurePropertiesLoaded())) return
  editingTenant.value = tenant
  form.value = {
    id: tenant.id,
    property_id: tenant.property_id,
    name: tenant.name,
    phone: tenant.phone,
    contract_id: tenant.contract_id,
    payment_status: tenant.payment_status,
    move_in_date: tenant.move_in_date,
    lease_end: tenant.lease_end,
    balance: tenant.balance,
  }
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingTenant.value = null
  form.value = emptyForm()
  actionError.value = ''
}

async function saveTenant() {
  if (editingTenant.value) {
    if (!canUpdate.value) return
  } else if (!canCreate.value) {
    return
  }

  const validationError = validateForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  saving.value = true
  actionError.value = ''
  try {
    const successMessage = editingTenant.value ? '租客已更新' : '租客已新增'
    if (editingTenant.value) {
      await api.updateTenant(editingTenant.value.id, buildUpdatePayload())
    } else {
      await api.createTenant(buildCreatePayload())
    }
    closeForm()
    const [tenantsLoaded, propertiesLoaded] = await Promise.all([loadTenants(), loadProperties()])
    if (!tenantsLoaded || !propertiesLoaded) {
      actionError.value = `${successMessage}，但数据刷新失败，请手动刷新页面`
      return
    }
    ElMessage.success(successMessage)
  } catch (err) {
    actionError.value = errorMessage(err, '保存租客失败')
  } finally {
    saving.value = false
  }
}

async function deleteTenant(tenant: Tenant) {
  if (!canDelete.value) return

  try {
    await ElMessageBox.confirm(`确认删除租客 ${tenant.name}（${tenant.id}）吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }

  deletingId.value = tenant.id
  actionError.value = ''
  try {
    await api.deleteTenant(tenant.id)
    const [tenantsLoaded, propertiesLoaded] = await Promise.all([loadTenants(), loadProperties()])
    if (!tenantsLoaded || !propertiesLoaded) {
      actionError.value = '租客已删除，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('租客已删除')
  } catch (err) {
    actionError.value = errorMessage(err, '删除租客失败')
  } finally {
    deletingId.value = null
  }
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadTenants()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadTenants()
})

onMounted(() => {
  void loadTenants()
  void loadProperties()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="租客列表" description="维护租客联系方式、入住时间、关联合同和应收余额，减少人工查询成本。" action-label="新增租客" search-placeholder="搜索租客、电话、房间或合同" :action-permission="pageActionPermissions.tenantCreate" @action="openCreateForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <el-dialog v-model="showForm" :title="editingTenant ? '编辑租客' : '新增租客'" width="min(90vw, 720px)" @close="closeForm">
      <p class="mb-5 text-sm text-slate-500">选择关联房源并填写租客基础信息，保存后将同步房源入住状态。</p>
      <el-form label-position="top" :model="form">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <el-form-item label="租客编号" required>
            <el-input v-model="form.id" :disabled="!!editingTenant" placeholder="T-10006" />
          </el-form-item>
          <el-form-item label="关联房源" required>
            <el-select v-model="form.property_id" class="w-full" filterable placeholder="请选择房源">
              <el-option v-for="property in selectableProperties" :key="property.id" :label="`${property.building}-${property.room}（${property.id}）`" :value="property.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="租客姓名" required>
            <el-input v-model="form.name" placeholder="租客姓名" />
          </el-form-item>
          <el-form-item label="联系方式" required>
            <el-input v-model="form.phone" placeholder="手机号" />
          </el-form-item>
          <el-form-item label="合同编号" required>
            <el-input v-model="form.contract_id" placeholder="C-2026-0001" />
          </el-form-item>
          <el-form-item label="付款状态" required>
            <el-select v-model="form.payment_status" class="w-full">
              <el-option v-for="option in paymentStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="入住日期" required>
            <el-date-picker v-model="form.move_in_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="租约结束日" required>
            <el-date-picker v-model="form.lease_end" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="当前余额" required>
            <el-input-number v-model="form.balance" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTenant">保存租客</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" class="rounded-2xl">
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[1050px]" :data="paginatedTenants" empty-text="暂无租客数据" row-key="id">
        <el-table-column label="租客" min-width="150">
          <template #default="{ row }">
            <p class="font-semibold text-slate-950">{{ row.name }}</p>
            <p class="text-xs text-slate-500">{{ row.id }}</p>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="联系方式" min-width="130" />
        <el-table-column prop="room" label="房间" min-width="100">
          <template #default="{ row }">
            <span class="font-semibold">{{ row.room }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="contract_id" label="合同编号" min-width="130" />
        <el-table-column label="入住/到期" min-width="190">
          <template #default="{ row }">{{ row.move_in_date }} / {{ row.lease_end }}</template>
        </el-table-column>
        <el-table-column label="付款状态" min-width="110">
          <template #default="{ row }">
            <StatusChip :status="row.payment_status" />
          </template>
        </el-table-column>
        <el-table-column label="当前余额" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold tabular" :class="row.balance > 0 ? 'text-amber-700' : 'text-emerald-700'">{{ currency(row.balance) }}</span>
          </template>
        </el-table-column>
          <el-table-column v-if="hasActions" label="操作" width="150">
          <template #default="{ row }">
            <div class="flex gap-2">
              <el-button v-if="canUpdate" size="small" @click="openEditForm(asTenant(row))">编辑</el-button>
              <el-button v-if="canDelete" size="small" type="danger" plain :loading="deletingId === row.id" @click="deleteTenant(asTenant(row))">删除</el-button>
            </div>
          </template>
        </el-table-column>
        </el-table>
      </div>
      <el-pagination
        class="mt-4 justify-end"
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="pageSizes"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>
  </section>
</template>
