<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElMessageBox, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { pageActionPermissions, pagePermissions } from '@/config/permissions'
import { ApiError, api, currency, downloadBlob } from '@/services/api'
import type { Contract, ContractCreatePayload, ContractRenewalRequest, ContractUpdatePayload, DepositSettlementRequest, MoveOut, MoveOutRequest, Property } from '@/types/domain'

interface ContractForm {
  id: string
  property_id: string
  tenant: string
  start_date: string | null
  end_date: string | null
  monthly_rent: number | null
  deposit: number | null
}

interface RenewalForm {
  new_end_date: string | null
  monthly_rent: number | null
  deposit: number | null
}

interface SettlementForm {
  move_out_date: string | null
  reason: string
  rent_deduction: number | null
  utility_deduction: number | null
  damage_deduction: number | null
  cleaning_deduction: number | null
  other_deduction: number | null
  settled_date: string | null
  method: string
  note: string
}

const emptyForm = (): ContractForm => ({
  id: '',
  property_id: '',
  tenant: '',
  start_date: '',
  end_date: '',
  monthly_rent: 0,
  deposit: 0,
})

const emptyRenewalForm = (): RenewalForm => ({
  new_end_date: '',
  monthly_rent: 0,
  deposit: 0,
})

const emptySettlementForm = (): SettlementForm => ({
  move_out_date: '',
  reason: '',
  rent_deduction: 0,
  utility_deduction: 0,
  damage_deduction: 0,
  cleaning_deduction: 0,
  other_deduction: 0,
  settled_date: '',
  method: '银行转账',
  note: '退租押金结算',
})

const { hasPermission } = usePermissions()
const contracts = ref<Contract[]>([])
const properties = ref<Property[]>([])
const moveOutsByContract = ref<Record<string, MoveOut[]>>({})
const propertiesLoaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const exportingSettlements = ref(false)
const actionId = ref<string | null>(null)
const showForm = ref(false)
const showRenewalForm = ref(false)
const showSettlementForm = ref(false)
const editingContract = ref<Contract | null>(null)
const lifecycleContract = ref<Contract | null>(null)
const form = ref<ContractForm>(emptyForm())
const renewalForm = ref<RenewalForm>(emptyRenewalForm())
const settlementForm = ref<SettlementForm>(emptySettlementForm())
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let contractsRequestId = 0

const canCreate = computed(() => hasPermission(pageActionPermissions.contractCreate))
const canApprove = computed(() => hasPermission(pageActionPermissions.contractApprove))
const canTerminate = computed(() => hasPermission(pageActionPermissions.contractTerminate))
const canSettle = computed(() => canTerminate.value && hasPermission(pageActionPermissions.financeConfirm))
const canExportSettlements = computed(() => hasPermission(pagePermissions.finance) && hasPermission(pageActionPermissions.financeExport))
const hasActions = computed(() => canCreate.value || canApprove.value || canTerminate.value || canSettle.value)
const deductionFields = ['rent_deduction', 'utility_deduction', 'damage_deduction', 'cleaning_deduction', 'other_deduction'] as const
const deductionLabels: Record<(typeof deductionFields)[number], string> = {
  rent_deduction: '租金扣款',
  utility_deduction: '水电扣款',
  damage_deduction: '损坏扣款',
  cleaning_deduction: '保洁扣款',
  other_deduction: '其他扣款',
}

const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedContracts = computed(() => contracts.value)
const expiringSoon = computed(() => contracts.value.filter((contract) => contract.status === 'expiring' || (contract.status === 'active' && contract.days_left <= 30)).length)
const pendingContracts = computed(() => contracts.value.filter((contract) => contract.status === 'pending').length)
const activeContracts = computed(() => contracts.value.filter((contract) => contract.status === 'active' || contract.status === 'expiring').length)
const archivedContracts = computed(() => contracts.value.filter((contract) => contract.status === 'terminated').length)
const selectableProperties = computed(() => properties.value.filter((property) => property.status === 'vacant' || property.id === editingContract.value?.property_id))
const pendingMoveOutContractIds = computed(() => new Set(Object.entries(moveOutsByContract.value).filter(([, items]) => items.some((moveOut) => moveOut.status === 'pending_settlement')).map(([contractId]) => contractId)))
const totalDeductions = computed(() => deductionFields.reduce((sum, field) => sum + Number(settlementForm.value[field] ?? 0), 0))
const refundPreview = computed(() => Math.max((lifecycleContract.value?.deposit ?? 0) - totalDeductions.value, 0))

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

function validateForm() {
  if (!editingContract.value && !form.value.id.trim()) return '请输入合同编号'
  if (!form.value.property_id) return '请选择房源'
  if (!form.value.tenant.trim()) return '请输入租客姓名'
  if (!form.value.start_date) return '请选择开始日期'
  if (!form.value.end_date) return '请选择结束日期'
  if (form.value.end_date < form.value.start_date) return '结束日期不能早于开始日期'
  if (form.value.monthly_rent === null || !Number.isFinite(form.value.monthly_rent) || form.value.monthly_rent < 0 || !Number.isInteger(form.value.monthly_rent)) return '月租金必须是非负整数'
  if (form.value.deposit === null || !Number.isFinite(form.value.deposit) || form.value.deposit < 0 || !Number.isInteger(form.value.deposit)) return '押金必须是非负整数'
  return ''
}

function validateRenewalForm() {
  if (!lifecycleContract.value) return '请选择合同'
  if (!renewalForm.value.new_end_date) return '请选择新的结束日期'
  if (renewalForm.value.new_end_date <= lifecycleContract.value.end_date) return '新结束日期必须晚于当前结束日期'
  if (renewalForm.value.monthly_rent === null || !Number.isFinite(renewalForm.value.monthly_rent) || renewalForm.value.monthly_rent < 0 || !Number.isInteger(renewalForm.value.monthly_rent)) return '月租金必须是非负整数'
  if (renewalForm.value.deposit === null || !Number.isFinite(renewalForm.value.deposit) || renewalForm.value.deposit < 0 || !Number.isInteger(renewalForm.value.deposit)) return '押金必须是非负整数'
  return ''
}

function validateSettlementForm() {
  if (!lifecycleContract.value) return '请选择合同'
  if (!settlementForm.value.move_out_date) return '请选择退租日期'
  if (!settlementForm.value.reason.trim()) return '请输入退租原因'
  for (const field of deductionFields) {
    const value = settlementForm.value[field]
    if (value === null || !Number.isFinite(value) || value < 0 || !Number.isInteger(value)) return `${deductionLabels[field]}必须是非负整数`
  }
  if (lifecycleContract.value && totalDeductions.value > lifecycleContract.value.deposit) return '扣款合计不能超过押金'
  if (!settlementForm.value.settled_date) return '请选择结算日期'
  if (settlementForm.value.settled_date < settlementForm.value.move_out_date) return '结算日期不能早于退租日期'
  if (!settlementForm.value.method.trim()) return '请输入退款方式'
  if (settlementForm.value.method.trim().length > 40) return '退款方式不能超过 40 个字符'
  if (settlementForm.value.note.trim().length > 120) return '退款备注不能超过 120 个字符'
  return ''
}

function buildUpdatePayload(): ContractUpdatePayload {
  return {
    property_id: form.value.property_id,
    tenant: form.value.tenant.trim(),
    start_date: form.value.start_date ?? '',
    end_date: form.value.end_date ?? '',
    monthly_rent: Number(form.value.monthly_rent),
    deposit: Number(form.value.deposit),
  }
}

function buildCreatePayload(): ContractCreatePayload {
  return {
    id: form.value.id.trim(),
    ...buildUpdatePayload(),
  }
}

function buildRenewalPayload(): ContractRenewalRequest {
  return {
    new_end_date: renewalForm.value.new_end_date ?? '',
    monthly_rent: Number(renewalForm.value.monthly_rent),
    deposit: Number(renewalForm.value.deposit),
  }
}

function buildMoveOutPayload(): MoveOutRequest {
  return {
    move_out_date: settlementForm.value.move_out_date ?? '',
    reason: settlementForm.value.reason.trim(),
  }
}

function canOpenSettlement(contract: Contract) {
  return canSettle.value && (['active', 'expiring'].includes(contract.status) || pendingMoveOutContractIds.value.has(contract.id))
}

function buildSettlementPayload(): DepositSettlementRequest {
  return {
    deductions: totalDeductions.value,
    rent_deduction: Number(settlementForm.value.rent_deduction),
    utility_deduction: Number(settlementForm.value.utility_deduction),
    damage_deduction: Number(settlementForm.value.damage_deduction),
    cleaning_deduction: Number(settlementForm.value.cleaning_deduction),
    other_deduction: Number(settlementForm.value.other_deduction),
    settled_date: settlementForm.value.settled_date ?? '',
    method: settlementForm.value.method.trim(),
    note: settlementForm.value.note.trim(),
  }
}

async function loadContracts() {
  const requestId = ++contractsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.contracts({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== contractsRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    contracts.value = response.items
    normalizeCurrentPage()
    const terminatedContracts = contracts.value.filter((contract) => contract.status === 'terminated')
    const moveOuts = await Promise.all(terminatedContracts.map(async (contract) => [contract.id, await api.contractMoveOuts(contract.id)] as const))
    if (requestId !== contractsRequestId) return false
    moveOutsByContract.value = Object.fromEntries(moveOuts)
    return true
  } catch (err) {
    if (requestId === contractsRequestId) {
      loadError.value = errorMessage(err, '合同加载失败')
    }
    return false
  } finally {
    if (requestId === contractsRequestId) {
      loading.value = false
    }
  }
}

async function loadProperties() {
  try {
    properties.value = await api.contractPropertyOptions()
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
  editingContract.value = null
  if (!(await ensurePropertiesLoaded())) return
  form.value = emptyForm()
  showForm.value = true
}

function asContract(row: unknown): Contract {
  return row as Contract
}

async function openEditForm(contract: Contract) {
  if (!canCreate.value || contract.status !== 'pending') return
  actionError.value = ''
  if (!(await ensurePropertiesLoaded())) return
  editingContract.value = contract
  form.value = {
    id: contract.id,
    property_id: contract.property_id,
    tenant: contract.tenant,
    start_date: contract.start_date,
    end_date: contract.end_date,
    monthly_rent: contract.monthly_rent,
    deposit: contract.deposit,
  }
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingContract.value = null
  form.value = emptyForm()
  actionError.value = ''
}

function openRenewalForm(contract: Contract) {
  if (!canApprove.value || !['active', 'expiring'].includes(contract.status)) return
  actionError.value = ''
  lifecycleContract.value = contract
  renewalForm.value = {
    new_end_date: contract.end_date,
    monthly_rent: contract.monthly_rent,
    deposit: contract.deposit,
  }
  showSettlementForm.value = false
  showRenewalForm.value = true
}

function closeRenewalForm() {
  showRenewalForm.value = false
  lifecycleContract.value = null
  renewalForm.value = emptyRenewalForm()
  actionError.value = ''
}

function openSettlementForm(contract: Contract) {
  if (!canOpenSettlement(contract)) return
  actionError.value = ''
  lifecycleContract.value = contract
  const pendingMoveOut = moveOutsByContract.value[contract.id]?.find((moveOut) => moveOut.status === 'pending_settlement')
  settlementForm.value = {
    ...emptySettlementForm(),
    move_out_date: pendingMoveOut?.move_out_date ?? '',
    reason: pendingMoveOut?.reason ?? '',
  }
  showRenewalForm.value = false
  showSettlementForm.value = true
}

function closeSettlementForm() {
  showSettlementForm.value = false
  lifecycleContract.value = null
  settlementForm.value = emptySettlementForm()
  actionError.value = ''
}

async function refreshLifecycleData(successMessage: string) {
  notifyTasksUpdated()
  const [contractsLoaded, propertiesLoaded] = await Promise.all([loadContracts(), loadProperties()])
  if (!contractsLoaded || !propertiesLoaded) {
    actionError.value = `${successMessage}，但数据刷新失败，请手动刷新页面`
    return false
  }
  ElMessage.success(successMessage)
  return true
}

async function saveContract() {
  if (!canCreate.value) return

  const validationError = validateForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  saving.value = true
  actionError.value = ''
  try {
    const successMessage = editingContract.value ? '合同已更新' : '合同已新建'
    if (editingContract.value) {
      await api.updateContract(editingContract.value.id, buildUpdatePayload())
    } else {
      await api.createContract(buildCreatePayload())
    }
    notifyTasksUpdated()
    closeForm()
    const [contractsLoaded, propertiesLoaded] = await Promise.all([loadContracts(), loadProperties()])
    if (!contractsLoaded || !propertiesLoaded) {
      actionError.value = `${successMessage}，但数据刷新失败，请手动刷新页面`
      return
    }
    ElMessage.success(successMessage)
  } catch (err) {
    actionError.value = errorMessage(err, '保存合同失败')
  } finally {
    saving.value = false
  }
}

async function renewContract() {
  if (!canApprove.value || !lifecycleContract.value) return

  const validationError = validateRenewalForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  const contract = lifecycleContract.value
  actionId.value = contract.id
  actionError.value = ''
  try {
    await api.renewContract(contract.id, buildRenewalPayload())
    closeRenewalForm()
    await refreshLifecycleData('合同已续签')
  } catch (err) {
    actionError.value = errorMessage(err, '续签合同失败')
  } finally {
    actionId.value = null
  }
}

async function exportSettlements() {
  if (!canExportSettlements.value) return
  exportingSettlements.value = true
  actionError.value = ''
  try {
    downloadBlob(await api.exportDepositSettlements(), 'deposit-settlements.csv')
  } catch (err) {
    actionError.value = errorMessage(err, '导出结算失败')
  } finally {
    exportingSettlements.value = false
  }
}

async function settleMoveOut() {
  if (!canSettle.value || !lifecycleContract.value) return

  const validationError = validateSettlementForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  const contract = lifecycleContract.value
  try {
    await ElMessageBox.confirm(
      `确认提交合同 ${contract.id}（${contract.tenant}）退租结算吗？扣款合计 ${currency(totalDeductions.value)}，预计退还 ${currency(refundPreview.value)}。`,
      '退租结算确认',
      {
        confirmButtonText: '提交结算',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  actionId.value = contract.id
  actionError.value = ''
  try {
    const moveOuts = await api.contractMoveOuts(contract.id)
    const moveOut = moveOuts[0]
    if (moveOut) {
      if (moveOut.status === 'settled') {
        throw new Error('该合同已完成退租结算')
      }
      if (moveOut.move_out_date !== settlementForm.value.move_out_date || moveOut.reason !== settlementForm.value.reason.trim()) {
        throw new Error('该合同已有待结算退租记录，请使用原退租日期和原因完成结算')
      }
    }
    const targetMoveOut = moveOut ?? await api.createMoveOut(contract.id, buildMoveOutPayload())
    await api.settleMoveOut(targetMoveOut.id, buildSettlementPayload())
    closeSettlementForm()
    await refreshLifecycleData('退租结算已完成')
  } catch (err) {
    actionError.value = errorMessage(err, '退租结算失败')
  } finally {
    actionId.value = null
  }
}

async function approveContract(contract: Contract) {
  if (!canApprove.value || contract.status !== 'pending') return
  actionId.value = contract.id
  actionError.value = ''
  try {
    await api.approveContract(contract.id)
    notifyTasksUpdated()
    const contractsLoaded = await loadContracts()
    if (!contractsLoaded) {
      actionError.value = '合同已审批，但数据刷新失败，请手动刷新页面'
      return
    }
    if (canCreate.value && propertiesLoaded.value && !(await loadProperties())) {
      actionError.value = '合同已审批，但房源选项刷新失败，请重新打开表单'
      return
    }
    ElMessage.success('合同已审批生效')
  } catch (err) {
    actionError.value = errorMessage(err, '审批合同失败')
  } finally {
    actionId.value = null
  }
}

async function terminateContract(contract: Contract) {
  if (!canTerminate.value || !['pending', 'active', 'expiring'].includes(contract.status)) return

  try {
    await ElMessageBox.confirm(`确认终止合同 ${contract.id} 吗？`, '终止确认', {
      confirmButtonText: '终止',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }

  actionId.value = contract.id
  actionError.value = ''
  try {
    await api.terminateContract(contract.id)
    notifyTasksUpdated()
    const contractsLoaded = await loadContracts()
    if (!contractsLoaded) {
      actionError.value = '合同已终止，但数据刷新失败，请手动刷新页面'
      return
    }
    if (canCreate.value && propertiesLoaded.value && !(await loadProperties())) {
      actionError.value = '合同已终止，但房源选项刷新失败，请重新打开表单'
      return
    }
    ElMessage.success('合同已终止')
  } catch (err) {
    actionError.value = errorMessage(err, '终止合同失败')
  } finally {
    actionId.value = null
  }
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadContracts()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadContracts()
})

onMounted(() => {
  void loadContracts()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="合同管理中心" description="跟踪合同签署、生效、到期与终止状态，提前识别租约风险并推动续签。" action-label="新建合同" search-placeholder="搜索合同、租客、房间或状态" :action-permission="pageActionPermissions.contractCreate" @action="openCreateForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <div class="grid grid-cols-1 gap-5 xl:grid-cols-[0.75fr_1.25fr]">
      <el-card shadow="never" class="rounded-2xl">
        <p class="eyebrow">本页 Lease Risk</p>
        <h2 class="section-title mt-2">本页到期提醒</h2>
        <div class="mt-5 space-y-4">
          <div class="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-100">
            <p class="text-sm font-semibold text-amber-800">本页 30 天内到期</p>
            <p class="mt-2 text-3xl font-bold text-amber-700 tabular">{{ expiringSoon }}</p>
          </div>
          <div class="rounded-2xl bg-rose-50 p-4 ring-1 ring-rose-100">
            <p class="text-sm font-semibold text-rose-800">本页待签署合同</p>
            <p class="mt-2 text-3xl font-bold text-rose-700 tabular">{{ pendingContracts }}</p>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="rounded-2xl">
        <div class="flex items-center justify-between">
          <div>
            <p class="eyebrow">本页 Contract Pipeline</p>
            <h2 class="section-title mt-2">本页合同流程</h2>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <el-button v-if="canExportSettlements" type="primary" plain :loading="exportingSettlements" @click="exportSettlements">导出结算</el-button>
            <el-tag type="success" effect="plain" round>{{ total }} 份匹配合同</el-tag>
          </div>
        </div>
        <div class="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div v-for="step in [
            { label: '本页草拟', value: pendingContracts },
            { label: '本页待签署', value: pendingContracts },
            { label: '本页已生效', value: activeContracts },
            { label: '本页归档', value: archivedContracts },
          ]" :key="step.label" class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p class="text-sm font-semibold text-slate-600">{{ step.label }}</p>
            <p class="mt-3 text-2xl font-bold tabular text-slate-950">{{ step.value }}</p>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="showForm" width="860px" :before-close="closeForm">
      <template #header>
        <div>
          <p class="eyebrow">{{ editingContract ? 'Edit Contract' : 'Create Contract' }}</p>
          <h2 class="mt-2 text-xl font-bold text-slate-950">{{ editingContract ? '编辑待签合同' : '新建合同' }}</h2>
          <p class="mt-1 text-sm text-slate-500">选择房源并填写租约信息，新建合同默认为待处理状态。</p>
        </div>
      </template>

      <el-form label-position="top" :model="form">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <el-form-item label="合同编号" required>
            <el-input v-model="form.id" :disabled="!!editingContract" placeholder="C-2026-0001" />
          </el-form-item>
          <el-form-item label="关联房源" required>
            <el-select v-model="form.property_id" class="w-full" filterable placeholder="请选择房源">
              <el-option v-for="property in selectableProperties" :key="property.id" :label="`${property.building}-${property.room}（${property.id}）`" :value="property.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="租客姓名" required>
            <el-input v-model="form.tenant" placeholder="租客姓名" />
          </el-form-item>
          <el-form-item label="开始日期" required>
            <el-date-picker v-model="form.start_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="结束日期" required>
            <el-date-picker v-model="form.end_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="月租金" required>
            <el-input-number v-model="form.monthly_rent" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
          <el-form-item label="押金" required>
            <el-input-number v-model="form.deposit" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeForm">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveContract">保存合同</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showRenewalForm" width="760px" :before-close="closeRenewalForm">
      <template v-if="lifecycleContract" #header>
        <div>
          <p class="eyebrow">Renew Contract</p>
          <h2 class="mt-2 text-xl font-bold text-slate-950">合同续签</h2>
          <p class="mt-1 text-sm text-slate-500">{{ lifecycleContract.id }}：{{ lifecycleContract.tenant }}，当前租期至 {{ lifecycleContract.end_date }}</p>
        </div>
      </template>
      <el-form v-if="lifecycleContract" label-position="top" :model="renewalForm">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <el-form-item label="新结束日期" required>
            <el-date-picker v-model="renewalForm.new_end_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="月租金" required>
            <el-input-number v-model="renewalForm.monthly_rent" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
          <el-form-item label="押金" required>
            <el-input-number v-model="renewalForm.deposit" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
        </div>
      </el-form>
      <template v-if="lifecycleContract" #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeRenewalForm">取消</el-button>
          <el-button type="primary" :loading="actionId === lifecycleContract.id" @click="renewContract">确认续签</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showSettlementForm" width="920px" :before-close="closeSettlementForm">
      <template v-if="lifecycleContract" #header>
        <div>
          <p class="eyebrow">Move-out Settlement</p>
          <h2 class="mt-2 text-xl font-bold text-slate-950">退租结算</h2>
          <p class="mt-1 text-sm text-slate-500">{{ lifecycleContract.id }}：{{ lifecycleContract.tenant }}，押金 {{ currency(lifecycleContract.deposit) }}</p>
        </div>
      </template>
      <el-form v-if="lifecycleContract" label-position="top" :model="settlementForm">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <el-form-item label="退租日期" required>
            <el-date-picker v-model="settlementForm.move_out_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="退租原因" required>
            <el-input v-model="settlementForm.reason" placeholder="到期不续租/提前退租" />
          </el-form-item>
          <el-form-item v-for="field in deductionFields" :key="field" :label="deductionLabels[field]" required>
            <el-input-number v-model="settlementForm[field]" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
          <el-form-item label="结算日期" required>
            <el-date-picker v-model="settlementForm.settled_date" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="退款方式" required>
            <el-input v-model="settlementForm.method" placeholder="银行转账" />
          </el-form-item>
          <el-form-item label="退款备注">
            <el-input v-model="settlementForm.note" placeholder="退租押金结算" />
          </el-form-item>
        </div>
        <div class="mt-2 grid grid-cols-1 gap-3 rounded-2xl bg-slate-50 p-4 md:grid-cols-3">
          <div>
            <p class="text-xs font-semibold text-slate-500">押金</p>
            <p class="mt-1 text-lg font-bold text-slate-950 tabular">{{ currency(lifecycleContract.deposit) }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-500">扣款合计</p>
            <p class="mt-1 text-lg font-bold text-amber-700 tabular">{{ currency(totalDeductions) }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-500">预计退还</p>
            <p class="mt-1 text-lg font-bold text-emerald-700 tabular">{{ currency(refundPreview) }}</p>
          </div>
        </div>
      </el-form>
      <template v-if="lifecycleContract" #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="closeSettlementForm">取消</el-button>
          <el-button type="primary" :loading="actionId === lifecycleContract.id" @click="settleMoveOut">提交结算</el-button>
        </div>
      </template>
    </el-dialog>

    <el-card shadow="never" class="rounded-2xl">
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[1120px]" :data="paginatedContracts" empty-text="暂无合同数据" row-key="id">
        <el-table-column prop="id" label="合同编号" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-slate-950">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="租客/房间" min-width="150">
          <template #default="{ row }">
            <p class="font-semibold">{{ row.tenant }}</p>
            <p class="text-xs text-slate-500">{{ row.room }}</p>
          </template>
        </el-table-column>
        <el-table-column label="租期" min-width="210">
          <template #default="{ row }">{{ row.start_date }} 至 {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="月租金" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold tabular">{{ currency(row.monthly_rent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="押金" min-width="120">
          <template #default="{ row }">{{ currency(row.deposit) }}</template>
        </el-table-column>
        <el-table-column label="剩余天数" min-width="110">
          <template #default="{ row }">
            <span class="font-semibold tabular" :class="row.days_left < 60 ? 'text-amber-700' : 'text-slate-700'">{{ row.days_left }} 天</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.status" />
          </template>
        </el-table-column>
          <el-table-column v-if="hasActions" label="操作" width="320">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-2">
              <el-button v-if="canCreate && row.status === 'pending'" size="small" @click="openEditForm(asContract(row))">编辑</el-button>
              <el-button v-if="canApprove && row.status === 'pending'" size="small" type="primary" plain :loading="actionId === row.id" @click="approveContract(asContract(row))">审批</el-button>
              <el-button v-if="canApprove && ['active', 'expiring'].includes(row.status)" size="small" type="primary" plain :loading="actionId === row.id" @click="openRenewalForm(asContract(row))">续签</el-button>
              <el-button v-if="canOpenSettlement(asContract(row))" size="small" type="warning" plain :loading="actionId === row.id" @click="openSettlementForm(asContract(row))">退租结算</el-button>
              <el-button v-if="canTerminate && ['pending', 'active', 'expiring'].includes(row.status)" size="small" type="danger" plain :loading="actionId === row.id" @click="terminateContract(asContract(row))">终止</el-button>
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
