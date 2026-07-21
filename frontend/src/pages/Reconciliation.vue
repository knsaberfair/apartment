<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElPagination, ElTable, ElTableColumn } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { pageActionPermissions } from '@/config/permissions'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api, currency, downloadBlob } from '@/services/api'
import type { ReconciliationImportPayload, ReconciliationRecord, ReconciliationRecordCreatePayload } from '@/types/domain'

interface ReconciliationFormItem extends Omit<ReconciliationRecordCreatePayload, 'date'> {
  key: string
  date: string | null
}

interface ReconciliationForm {
  records: ReconciliationFormItem[]
}

let reconciliationRowId = 0

const createRecord = (): ReconciliationFormItem => ({
  key: `reconciliation-row-${reconciliationRowId += 1}`,
  id: '',
  date: '',
  bank_flow_id: '',
  system_flow_id: '',
  payer: '',
  amount: 0,
  channel: '',
})

const emptyForm = (): ReconciliationForm => ({
  records: [createRecord()],
})

const records = ref<ReconciliationRecord[]>([])
const form = ref<ReconciliationForm>(emptyForm())
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const actionId = ref<string | null>(null)
const showForm = ref(false)
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let recordsRequestId = 0
const { hasPermission } = usePermissions()

const canImport = computed(() => hasPermission(pageActionPermissions.reconciliationImport))
const canResolve = computed(() => hasPermission(pageActionPermissions.reconciliationResolve))
const canExport = computed(() => hasPermission(pageActionPermissions.reconciliationExport))
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedRecords = computed(() => records.value)
const matchedCount = computed(() => records.value.filter((record) => record.status === 'matched').length)
const pendingCount = computed(() => records.value.filter((record) => record.status === 'pending').length)
const exceptionCount = computed(() => records.value.filter((record) => record.status === 'exception').length)

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

async function loadRecords() {
  const requestId = ++recordsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.reconciliation({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== recordsRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    records.value = response.items
    normalizeCurrentPage()
    return true
  } catch (err) {
    if (requestId === recordsRequestId) {
      loadError.value = errorMessage(err, '对账记录加载失败')
    }
    return false
  } finally {
    if (requestId === recordsRequestId) {
      loading.value = false
    }
  }
}

function openImportForm() {
  if (!canImport.value) return
  form.value = emptyForm()
  actionError.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  form.value = emptyForm()
  actionError.value = ''
}

function addImportRow() {
  if (form.value.records.length >= 100) return
  form.value.records.push(createRecord())
}

function removeImportRow(index: number) {
  if (form.value.records.length === 1) return
  form.value.records.splice(index, 1)
}

function validateRecord(record: ReconciliationFormItem, index: number) {
  const prefix = form.value.records.length > 1 ? `第 ${index + 1} 行` : ''
  if (!record.id.trim()) return `${prefix}请输入对账编号`
  if (!record.date) return `${prefix}请选择日期`
  if (!record.bank_flow_id.trim()) return `${prefix}请输入银行流水`
  if (!record.system_flow_id.trim()) return `${prefix}请输入系统流水`
  if (!record.payer.trim()) return `${prefix}请输入付款方`
  if (typeof record.amount !== 'number' || !Number.isFinite(record.amount) || record.amount === 0) return `${prefix}请输入非零金额`
  if (!record.channel.trim()) return `${prefix}请输入渠道`
  return ''
}

function validateForm() {
  for (const [index, record] of form.value.records.entries()) {
    const error = validateRecord(record, index)
    if (error) return error
  }
  return ''
}

function buildPayload(): ReconciliationImportPayload {
  return {
    records: form.value.records.map((record) => ({
      id: record.id.trim(),
      date: record.date ?? '',
      bank_flow_id: record.bank_flow_id.trim(),
      system_flow_id: record.system_flow_id.trim(),
      payer: record.payer.trim(),
      amount: record.amount,
      channel: record.channel.trim(),
    })),
  }
}

async function importRecord() {
  if (!canImport.value) return
  const validationError = validateForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  saving.value = true
  actionError.value = ''
  try {
    const imported = await api.importReconciliation(buildPayload())
    notifyTasksUpdated()
    closeForm()
    if (!(await loadRecords())) {
      actionError.value = '流水已导入，但数据刷新失败，请手动刷新页面'
      return
    }
    const summary = imported.reduce((acc, record) => {
      acc[record.status] = (acc[record.status] ?? 0) + 1
      return acc
    }, {} as Record<string, number>)
    ElMessage.success(`已导入 ${imported.length} 条流水，匹配 ${summary.matched ?? 0}，待处理 ${summary.pending ?? 0}，异常 ${summary.exception ?? 0}`)
  } catch (err) {
    actionError.value = errorMessage(err, '导入流水失败')
  } finally {
    saving.value = false
  }
}

function asRecord(row: unknown): ReconciliationRecord {
  return row as ReconciliationRecord
}

async function retryRecord(record: ReconciliationRecord) {
  if (!canResolve.value || record.status !== 'pending') return
  actionId.value = record.id
  actionError.value = ''
  try {
    await api.retryReconciliation(record.id)
    notifyTasksUpdated()
    if (!(await loadRecords())) {
      actionError.value = '已重试匹配，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('已重试匹配')
  } catch (err) {
    actionError.value = errorMessage(err, '重试匹配失败')
  } finally {
    actionId.value = null
  }
}

async function resolveRecord(record: ReconciliationRecord) {
  if (!canResolve.value || record.status !== 'exception') return
  actionId.value = record.id
  actionError.value = ''
  try {
    await api.resolveReconciliation(record.id)
    notifyTasksUpdated()
    if (!(await loadRecords())) {
      actionError.value = '对账记录已复核，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('对账记录已复核')
  } catch (err) {
    actionError.value = errorMessage(err, '标记复核失败')
  } finally {
    actionId.value = null
  }
}

async function exportRecords() {
  if (!canExport.value) return
  exporting.value = true
  actionError.value = ''
  try {
    downloadBlob(await api.exportReconciliation(), 'reconciliation-records.csv')
  } catch (err) {
    actionError.value = errorMessage(err, '下载对账单失败')
  } finally {
    exporting.value = false
  }
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadRecords()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadRecords()
})

onMounted(() => {
  void loadRecords()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="财务流水对账单" description="核对银行流水、第三方支付与系统账单差异，定位异常款项并沉淀审计记录。" action-label="导入流水" search-placeholder="搜索对账编号、流水、付款方或状态" :action-permission="pageActionPermissions.reconciliationImport" @action="openImportForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <el-dialog v-model="showForm" title="导入流水" width="960px" @close="closeForm">
      <el-form label-position="top" :model="form">
        <div class="mb-4 flex items-center justify-between gap-3">
          <p class="text-sm text-slate-500">一次最多导入 100 条流水，系统会逐条匹配财务账单。</p>
          <el-button plain :disabled="form.records.length >= 100" @click="addImportRow">新增一行</el-button>
        </div>
        <div class="space-y-4">
          <div v-for="(record, index) in form.records" :key="record.key" class="rounded-2xl border border-slate-200 p-4">
            <div class="mb-4 flex items-center justify-between">
              <p class="font-semibold text-slate-900">流水 {{ index + 1 }}</p>
              <el-button v-if="form.records.length > 1" type="danger" plain size="small" @click="removeImportRow(index)">删除</el-button>
            </div>
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
              <el-form-item label="对账编号" required>
                <el-input v-model="record.id" placeholder="R-20260715-001" />
              </el-form-item>
              <el-form-item label="日期" required>
                <el-date-picker v-model="record.date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
              </el-form-item>
              <el-form-item label="银行流水" required>
                <el-input v-model="record.bank_flow_id" placeholder="BK202607150001" />
              </el-form-item>
              <el-form-item label="系统流水" required>
                <el-input v-model="record.system_flow_id" placeholder="F-20260714-001" />
              </el-form-item>
              <el-form-item label="付款方" required>
                <el-input v-model="record.payer" placeholder="租客/供应商" />
              </el-form-item>
              <el-form-item label="金额" required>
                <el-input-number v-model="record.amount" class="w-full" :precision="0" :step="100" />
              </el-form-item>
              <el-form-item label="渠道" required>
                <el-input v-model="record.channel" placeholder="招商银行/支付宝" />
              </el-form-item>
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="importRecord">确认导入</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" class="rounded-2xl">
      <div class="flex items-center justify-between">
        <div>
          <p class="eyebrow">Reconciliation Summary</p>
          <h2 class="section-title mt-2">今日对账概览</h2>
        </div>
        <el-button v-if="canExport" type="primary" plain :loading="exporting" @click="exportRecords">下载对账单</el-button>
      </div>
      <div class="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-2xl bg-slate-50 p-4"><p class="text-sm text-slate-500">匹配流水</p><p class="mt-2 text-2xl font-bold tabular">{{ total }}</p></div>
        <div class="rounded-2xl bg-emerald-50 p-4"><p class="text-sm text-emerald-700">本页已匹配</p><p class="mt-2 text-2xl font-bold text-emerald-700 tabular">{{ matchedCount }}</p></div>
        <div class="rounded-2xl bg-amber-50 p-4"><p class="text-sm text-amber-700">本页待确认</p><p class="mt-2 text-2xl font-bold text-amber-700 tabular">{{ pendingCount }}</p></div>
        <div class="rounded-2xl bg-rose-50 p-4"><p class="text-sm text-rose-700">本页异常差额</p><p class="mt-2 text-2xl font-bold text-rose-700 tabular">{{ exceptionCount }}</p></div>
      </div>
    </el-card>

    <el-card shadow="never" class="rounded-2xl">
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[1080px]" :data="paginatedRecords" empty-text="暂无对账记录" row-key="id">
        <el-table-column prop="id" label="对账编号" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-slate-950">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" min-width="110" />
        <el-table-column prop="bank_flow_id" label="银行流水" min-width="130" />
        <el-table-column prop="system_flow_id" label="系统流水" min-width="130" />
        <el-table-column prop="payer" label="付款方" min-width="130">
          <template #default="{ row }">
            <span class="font-semibold">{{ row.payer }}</span>
          </template>
        </el-table-column>
        <el-table-column label="金额" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold tabular">{{ currency(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="channel" label="渠道" min-width="100" />
        <el-table-column label="差额" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold tabular" :class="row.difference === 0 ? 'text-emerald-700' : 'text-rose-700'">{{ currency(row.difference) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column v-if="canResolve" label="操作" fixed="right" min-width="150">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-2">
              <el-button v-if="row.status === 'pending'" size="small" type="warning" plain :loading="actionId === row.id" @click="retryRecord(asRecord(row))">重试匹配</el-button>
              <el-button v-if="row.status === 'exception'" size="small" type="warning" plain :loading="actionId === row.id" @click="resolveRecord(asRecord(row))">标记已复核</el-button>
              <span v-if="!['pending', 'exception'].includes(row.status)" class="text-xs text-slate-400">-</span>
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
