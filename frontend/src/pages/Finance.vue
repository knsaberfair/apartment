<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api, currency, downloadBlob } from '@/services/api'
import type { FinanceCreateStatus, FinanceTransaction, FinanceTransactionCreatePayload, PropertyOption } from '@/types/domain'

interface TransactionForm {
  id: string
  property_id: string
  date: string | null
  type: string
  tenant: string
  amount: number
  method: string
  status: FinanceCreateStatus
  note: string
}

const emptyForm = (): TransactionForm => ({
  id: '',
  property_id: '',
  date: '',
  type: '',
  tenant: '',
  amount: 0,
  method: '',
  status: 'paid',
  note: '',
})

const statusOptions: Array<{ label: string; value: FinanceCreateStatus }> = [
  { label: '已支付', value: 'paid' },
  { label: '待确认', value: 'pending' },
  { label: '逾期', value: 'overdue' },
]

const transactions = ref<FinanceTransaction[]>([])
const properties = ref<PropertyOption[]>([])
const propertiesLoaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const generatingRentBills = ref(false)
const actionId = ref<string | null>(null)
const showForm = ref(false)
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let transactionsRequestId = 0
const billingMonth = ref(new Date().toISOString().slice(0, 7))
const form = ref<TransactionForm>(emptyForm())
const { hasPermission } = usePermissions()

const canCreate = computed(() => hasPermission(pageActionPermissions.financeCreate))
const canConfirm = computed(() => hasPermission(pageActionPermissions.financeConfirm))
const canExport = computed(() => hasPermission(pageActionPermissions.financeExport))
const lifecycleLabels: Record<string, string> = {
  rent: '租金',
  renewal: '续签',
  settlement: '结算',
}
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedTransactions = computed(() => transactions.value)
const income = computed(() => transactions.value.filter((item) => item.amount > 0).reduce((sum, item) => sum + item.amount, 0))
const expense = computed(() => Math.abs(transactions.value.filter((item) => item.amount < 0).reduce((sum, item) => sum + item.amount, 0)))
const pending = computed(() => transactions.value.filter((item) => item.status === 'pending' || item.status === 'overdue').reduce((sum, item) => sum + Math.max(item.amount, 0), 0))

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

function notifyTasksUpdated() {
  window.dispatchEvent(new Event('apartment:tasks-updated'))
}

async function loadTransactions() {
  const requestId = ++transactionsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.transactions({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== transactionsRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    transactions.value = response.items
    normalizeCurrentPage()
    return true
  } catch (err) {
    if (requestId === transactionsRequestId) {
      loadError.value = errorMessage(err, '财务流水加载失败')
    }
    return false
  } finally {
    if (requestId === transactionsRequestId) {
      loading.value = false
    }
  }
}

async function loadProperties() {
  try {
    properties.value = await api.financePropertyOptions()
    propertiesLoaded.value = true
    return true
  } catch (err) {
    actionError.value = errorMessage(err, '房源选项加载失败')
    return false
  }
}

async function ensurePropertiesLoaded() {
  if (propertiesLoaded.value) return true
  return loadProperties()
}

async function openCreateForm() {
  if (!canCreate.value) return
  actionError.value = ''
  if (!(await ensurePropertiesLoaded())) return
  form.value = emptyForm()
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  form.value = emptyForm()
  actionError.value = ''
}

function validateForm() {
  const id = form.value.id.trim()
  if (!id) return '请输入流水编号'
  if (/^(RENT-|SETTLE-|RENEWAL-)/i.test(id)) return '流水编号不能使用 RENT-、SETTLE- 或 RENEWAL- 开头，这些前缀由系统生命周期账单保留'
  if (!form.value.property_id) return '请选择房源'
  if (!form.value.date) return '请选择日期'
  if (!form.value.type.trim()) return '请输入类型'
  if (typeof form.value.amount !== 'number' || !Number.isFinite(form.value.amount) || form.value.amount === 0) return '请输入非零金额'
  if (!form.value.method.trim()) return '请输入支付方式'
  return ''
}

function buildPayload(): FinanceTransactionCreatePayload {
  return {
    id: form.value.id.trim(),
    property_id: form.value.property_id,
    date: form.value.date ?? '',
    type: form.value.type.trim(),
    tenant: form.value.tenant.trim() || null,
    amount: form.value.amount,
    method: form.value.method.trim(),
    status: form.value.status,
    note: form.value.note.trim(),
  }
}

async function saveTransaction() {
  if (!canCreate.value) return
  const validationError = validateForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  saving.value = true
  actionError.value = ''
  try {
    await api.createTransaction(buildPayload())
    notifyTasksUpdated()
    closeForm()
    if (!(await loadTransactions())) {
      actionError.value = '账单已新增，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('账单已新增')
  } catch (err) {
    actionError.value = errorMessage(err, '新增账单失败')
  } finally {
    saving.value = false
  }
}

function asTransaction(row: unknown): FinanceTransaction {
  return row as FinanceTransaction
}

async function confirmTransaction(transaction: FinanceTransaction) {
  if (!canConfirm.value || !['pending', 'overdue'].includes(transaction.status)) return
  actionId.value = transaction.id
  actionError.value = ''
  try {
    await api.confirmTransaction(transaction.id)
    notifyTasksUpdated()
    if (!(await loadTransactions())) {
      actionError.value = '账单已确认，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('账单已确认支付')
  } catch (err) {
    actionError.value = errorMessage(err, '确认账单失败')
  } finally {
    actionId.value = null
  }
}

async function generateRentBills() {
  if (!canCreate.value) return
  if (!billingMonth.value) {
    actionError.value = '请选择账期月份'
    return
  }

  generatingRentBills.value = true
  actionError.value = ''
  try {
    const result = await api.generateRentBills({ month: billingMonth.value })
    notifyTasksUpdated()
    if (!(await loadTransactions())) {
      actionError.value = '租金账单已生成，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success(`租金账单生成完成：新增 ${result.created} 条，跳过 ${result.skipped} 条`)
  } catch (err) {
    actionError.value = errorMessage(err, '生成租金账单失败')
  } finally {
    generatingRentBills.value = false
  }
}

async function exportTransactions() {
  if (!canExport.value) return
  exporting.value = true
  actionError.value = ''
  try {
    downloadBlob(await api.exportTransactions(), 'finance-transactions.csv')
  } catch (err) {
    actionError.value = errorMessage(err, '导出流水失败')
  } finally {
    exporting.value = false
  }
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadTransactions()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadTransactions()
})

onMounted(() => {
  void loadTransactions()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="财务管理" description="汇总租金、押金、维修支出与待收账款，帮助财务人员快速完成月度运营核算。" action-label="新增账单" search-placeholder="搜索流水、类型、房间、租客或状态" :action-permission="pageActionPermissions.financeCreate" @action="openCreateForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <el-dialog v-model="showForm" title="新增账单" width="720px" @close="closeForm">
      <el-form label-position="top" :model="form">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <el-form-item label="流水编号" required>
            <el-input v-model="form.id" placeholder="F-20260715-001" />
          </el-form-item>
          <el-form-item label="关联房源" required>
            <el-select v-model="form.property_id" class="w-full" filterable placeholder="请选择房源">
              <el-option v-for="property in properties" :key="property.id" :label="`${property.building}-${property.room}（${property.id}）`" :value="property.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期" required>
            <el-date-picker v-model="form.date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="类型" required>
            <el-input v-model="form.type" placeholder="租金收入/维修支出" />
          </el-form-item>
          <el-form-item label="租客/付款方">
            <el-input v-model="form.tenant" placeholder="为空则使用房源当前租客" />
          </el-form-item>
          <el-form-item label="金额" required>
            <el-input-number v-model="form.amount" class="w-full" :precision="0" :step="100" />
          </el-form-item>
          <el-form-item label="支付方式" required>
            <el-input v-model="form.method" placeholder="银行转账/支付宝" />
          </el-form-item>
          <el-form-item label="状态" required>
            <el-select v-model="form.status" class="w-full">
              <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.note" placeholder="账单说明" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTransaction">保存账单</el-button>
      </template>
    </el-dialog>

    <div class="grid grid-cols-1 gap-5 md:grid-cols-3">
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页收入</p><p class="mt-3 text-3xl font-bold text-emerald-700 tabular">{{ currency(income) }}</p><p class="mt-2 text-sm text-slate-500">含租金与押金收入</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页支出</p><p class="mt-3 text-3xl font-bold text-rose-700 tabular">{{ currency(expense) }}</p><p class="mt-2 text-sm text-slate-500">维修与运营支出</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">待确认/逾期</p><p class="mt-3 text-3xl font-bold text-amber-700 tabular">{{ currency(pending) }}</p><p class="mt-2 text-sm text-slate-500">需跟进到账状态</p></el-card>
    </div>

    <el-card shadow="never" class="rounded-2xl">
      <template #header>
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div v-if="canCreate" class="flex flex-col gap-2 sm:flex-row sm:items-center">
            <el-date-picker v-model="billingMonth" class="w-full sm:w-40" type="month" value-format="YYYY-MM" placeholder="选择账期" />
            <el-button type="primary" plain :loading="generatingRentBills" @click="generateRentBills">生成租金账单</el-button>
          </div>
          <div class="flex justify-end">
            <el-button v-if="canExport" type="primary" plain :loading="exporting" @click="exportTransactions">导出流水</el-button>
          </div>
        </div>
      </template>
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[980px]" :data="paginatedTransactions" empty-text="暂无财务流水" row-key="id">
        <el-table-column prop="id" label="流水编号" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-slate-950">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" min-width="110" />
        <el-table-column prop="type" label="类型" min-width="110">
          <template #default="{ row }">
            <span class="font-semibold">{{ row.type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="房间/租客" min-width="150">
          <template #default="{ row }">
            <p class="font-semibold">{{ row.room }}</p>
            <p class="text-xs text-slate-500">{{ row.tenant }}</p>
          </template>
        </el-table-column>
        <el-table-column label="金额" min-width="120">
          <template #default="{ row }">
            <span class="font-bold tabular" :class="row.amount >= 0 ? 'text-emerald-700' : 'text-rose-700'">{{ currency(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="支付方式" min-width="110" />
        <el-table-column label="生命周期" min-width="160">
          <template #default="{ row }">
            <div v-if="row.lifecycle_type || row.contract_id || row.settlement_id" class="space-y-1 text-xs text-slate-500">
              <p v-if="row.lifecycle_type" class="font-semibold text-slate-700">{{ lifecycleLabels[row.lifecycle_type] ?? row.lifecycle_type }}</p>
              <p v-if="row.contract_id">合同：{{ row.contract_id }}</p>
              <p v-if="row.settlement_id">结算：{{ row.settlement_id }}</p>
            </div>
            <span v-else class="text-xs text-slate-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="150" />
        <el-table-column v-if="canConfirm" label="操作" fixed="right" min-width="130">
          <template #default="{ row }">
            <el-button v-if="['pending', 'overdue'].includes(row.status)" size="small" type="success" plain :loading="actionId === row.id" @click="confirmTransaction(asTransaction(row))">确认已支付</el-button>
            <span v-else class="text-xs text-slate-400">-</span>
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
