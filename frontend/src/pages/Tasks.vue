<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDialog, ElForm, ElFormItem, ElInput, ElMessage, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import { useServerPagination } from '@/composables/useServerPagination'
import { pageActionPermissions } from '@/config/permissions'
import { statusLabel } from '@/config/statusLabels'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api } from '@/services/api'
import type { TodoItem, TodoSeverity, TodoSource, TodoSummary } from '@/types/domain'

const sourceOptions: Array<{ label: string; value: TodoSource | 'all' }> = [
  { label: '全部来源', value: 'all' },
  { label: '合同', value: 'contracts' },
  { label: '工单', value: 'maintenance' },
  { label: '财务', value: 'finance' },
  { label: '对账', value: 'reconciliation' },
]

const severityOptions: Array<{ label: string; value: TodoSeverity | 'all' }> = [
  { label: '全部风险', value: 'all' },
  { label: '紧急', value: 'danger' },
  { label: '警示', value: 'warning' },
  { label: '提醒', value: 'info' },
]

const sourceLabels: Record<TodoSource, string> = {
  contracts: '合同',
  maintenance: '工单',
  finance: '财务',
  reconciliation: '对账',
}

const severityLabels: Record<TodoSeverity, string> = {
  danger: '紧急',
  warning: '警示',
  info: '提醒',
}

const severityTypes: Record<TodoSeverity, 'danger' | 'warning' | 'info'> = {
  danger: 'danger',
  warning: 'warning',
  info: 'info',
}

const summary = ref<TodoSummary | null>(null)
const loading = ref(false)
const actionId = ref<string | null>(null)
const loadError = ref('')
const actionError = ref('')
const sourceFilter = ref<TodoSource | 'all'>('all')
const severityFilter = ref<TodoSeverity | 'all'>('all')
let tasksRequestId = 0
const assigningTask = ref<TodoItem | null>(null)
const assignee = ref('')
const { hasPermission } = usePermissions()

const canApproveContract = computed(() => hasPermission(pageActionPermissions.contractApprove))
const canAssignMaintenance = computed(() => hasPermission(pageActionPermissions.maintenanceAssign))
const canResolveMaintenance = computed(() => hasPermission(pageActionPermissions.maintenanceResolve))
const canConfirmFinance = computed(() => hasPermission(pageActionPermissions.financeConfirm))
const canResolveReconciliation = computed(() => hasPermission(pageActionPermissions.reconciliationResolve))
const hasActions = computed(() => canApproveContract.value || canAssignMaintenance.value || canResolveMaintenance.value || canConfirmFinance.value || canResolveReconciliation.value)
const allItems = computed(() => summary.value?.items ?? [])
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedItems = computed(() => allItems.value)

const urgentItems = computed(() => allItems.value.filter((item) => item.severity === 'danger'))
const overdueItems = computed(() => allItems.value.filter((item) => isOverdue(item)))
const todayItems = computed(() => allItems.value.filter((item) => isToday(item)))
const upcomingItems = computed(() => allItems.value.filter((item) => isUpcoming(item)))
const sourceCount = computed(() => new Set(allItems.value.map((item) => item.source)).size)

const summaryCards = computed(() => [
  { label: '匹配提醒', value: total.value, tone: 'text-slate-950', hint: `${sourceCount.value} 个本页来源` },
  { label: '匹配紧急', value: summary.value?.urgent ?? 0, tone: 'text-rose-700', hint: '需优先处理' },
  { label: '匹配逾期', value: summary.value?.overdue ?? 0, tone: 'text-amber-700', hint: '超过截止日期' },
  { label: '本页今日', value: todayItems.value.length, tone: 'text-blue-700', hint: '今天需要处理' },
  { label: '本页 7 日内', value: upcomingItems.value.length, tone: 'text-emerald-700', hint: '近期提醒' },
])

const reminderGroups = computed(() => [
  { title: '本页紧急通知', description: '当前页风险最高的待处理事项', items: urgentItems.value.slice(0, 4), total: urgentItems.value.length, empty: '暂无紧急通知', accent: 'border-t-rose-400' },
  { title: '本页逾期提醒', description: '当前页超过截止日期仍未处理', items: overdueItems.value.slice(0, 4), total: overdueItems.value.length, empty: '暂无逾期提醒', accent: 'border-t-amber-400' },
  { title: '本页今日提醒', description: '当前页截止日期为今天的事项', items: todayItems.value.slice(0, 4), total: todayItems.value.length, empty: '暂无今日提醒', accent: 'border-t-blue-400' },
  { title: '本页近期提醒', description: '当前页未来 7 天内到期的事项', items: upcomingItems.value.slice(0, 4), total: upcomingItems.value.length, empty: '暂无近期提醒', accent: 'border-t-emerald-400' },
])

function dateOnly(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function dueDate(item: TodoItem) {
  if (!item.due_date) return null
  const date = new Date(`${item.due_date}T00:00:00`)
  return Number.isNaN(date.getTime()) ? null : dateOnly(date)
}

function isOverdue(item: TodoItem) {
  const due = dueDate(item)
  if (!due) return false
  return due.getTime() < dateOnly(new Date()).getTime()
}

function isToday(item: TodoItem) {
  const due = dueDate(item)
  if (!due) return false
  return due.getTime() === dateOnly(new Date()).getTime()
}

function isUpcoming(item: TodoItem) {
  const due = dueDate(item)
  if (!due) return false
  const today = dateOnly(new Date())
  const max = new Date(today)
  max.setDate(today.getDate() + 7)
  return due.getTime() > today.getTime() && due.getTime() <= max.getTime()
}

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

async function loadTasks() {
  const requestId = ++tasksRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.tasks({
      limit: pageSize.value,
      offset: offset.value,
      source: sourceFilter.value === 'all' ? undefined : sourceFilter.value,
      severity: severityFilter.value === 'all' ? undefined : severityFilter.value,
    })
    if (requestId !== tasksRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    summary.value = response
    normalizeCurrentPage()
    return true
  } catch (err) {
    if (requestId === tasksRequestId) {
      loadError.value = errorMessage(err, '通知提醒加载失败')
    }
    return false
  } finally {
    if (requestId === tasksRequestId) {
      loading.value = false
    }
  }
}

function sourceLabel(source: TodoSource) {
  return sourceLabels[source]
}

function severityLabel(severity: TodoSeverity) {
  return severityLabels[severity]
}

function severityType(severity: TodoSeverity) {
  return severityTypes[severity]
}

function rowAsTodo(row: unknown): TodoItem {
  return row as TodoItem
}

function canApproveTask(item: TodoItem) {
  return item.source === 'contracts' && item.status === 'pending' && canApproveContract.value
}

function canAssignTask(item: TodoItem) {
  return item.source === 'maintenance' && item.status === 'open' && canAssignMaintenance.value
}

function canResolveTask(item: TodoItem) {
  return item.source === 'maintenance' && item.status === 'in_progress' && canResolveMaintenance.value
}

function canConfirmTask(item: TodoItem) {
  return item.source === 'finance' && ['pending', 'overdue'].includes(item.status) && canConfirmFinance.value
}

function canRetryTask(item: TodoItem) {
  return item.source === 'reconciliation' && item.status === 'pending' && canResolveReconciliation.value
}

function canReviewTask(item: TodoItem) {
  return item.source === 'reconciliation' && item.status === 'exception' && canResolveReconciliation.value
}

function hasRowAction(item: TodoItem) {
  return canApproveTask(item) || canAssignTask(item) || canResolveTask(item) || canConfirmTask(item) || canRetryTask(item) || canReviewTask(item)
}

function openAssignTask(item: TodoItem) {
  if (!canAssignTask(item)) return
  assigningTask.value = item
  assignee.value = item.assignee && item.assignee !== '未分配' ? item.assignee : ''
  actionError.value = ''
}

function closeAssignTask() {
  assigningTask.value = null
  assignee.value = ''
  actionError.value = ''
}

async function assignTask() {
  if (!assigningTask.value || !canAssignTask(assigningTask.value)) return
  if (!assignee.value.trim()) {
    actionError.value = '请输入负责人'
    return
  }

  actionId.value = assigningTask.value.id
  actionError.value = ''
  try {
    await api.assignMaintenanceOrder(assigningTask.value.source_id, { assignee: assignee.value.trim() })
    closeAssignTask()
    notifyTasksUpdated()
    if (!(await loadTasks())) {
      actionError.value = '工单已派发，但通知提醒刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('工单已派发')
  } catch (err) {
    actionError.value = errorMessage(err, '派发工单失败')
  } finally {
    actionId.value = null
  }
}

async function runTaskAction(item: TodoItem) {
  actionId.value = item.id
  actionError.value = ''
  try {
    if (canApproveTask(item)) {
      await api.approveContract(item.source_id)
      ElMessage.success('合同已审批生效')
    } else if (canResolveTask(item)) {
      await api.resolveMaintenanceOrder(item.source_id)
      ElMessage.success('工单已完成')
    } else if (canConfirmTask(item)) {
      await api.confirmTransaction(item.source_id)
      ElMessage.success('账单已确认支付')
    } else if (canRetryTask(item)) {
      await api.retryReconciliation(item.source_id)
      ElMessage.success('已重试匹配')
    } else if (canReviewTask(item)) {
      await api.resolveReconciliation(item.source_id)
      ElMessage.success('对账记录已复核')
    } else {
      return
    }

    notifyTasksUpdated()
    if (!(await loadTasks())) {
      actionError.value = '操作已完成，但通知提醒刷新失败，请手动刷新页面'
      return
    }
  } catch (err) {
    actionError.value = errorMessage(err, '处理通知提醒失败')
  } finally {
    actionId.value = null
  }
}

function refreshTasks() {
  void loadTasks()
}

watch([sourceFilter, severityFilter], () => {
  if (currentPage.value === 1) {
    void loadTasks()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadTasks()
})

onMounted(() => {
  window.addEventListener('apartment:tasks-updated', refreshTasks)
  void loadTasks()
})

onUnmounted(() => {
  window.removeEventListener('apartment:tasks-updated', refreshTasks)
})
</script>

<template>
  <section class="space-y-6">
    <div class="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div class="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div class="max-w-2xl">
          <p class="eyebrow">Notification Center</p>
          <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">通知提醒中心</h1>
          <p class="mt-2 text-sm leading-6 text-slate-500">聚合合同、维修、财务与对账提醒，优先处理逾期、今日到期和高风险事项。</p>
        </div>
        <div class="rounded-2xl border border-slate-100 bg-slate-50 p-3">
          <p class="mb-2 text-xs font-semibold text-slate-500">筛选提醒</p>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-[160px_160px_auto]">
            <el-select v-model="sourceFilter" data-testid="source-filter" class="w-full" placeholder="来源">
              <el-option v-for="option in sourceOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-select v-model="severityFilter" data-testid="severity-filter" class="w-full" placeholder="风险">
              <el-option v-for="option in severityOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-button class="w-full sm:w-auto" :loading="loading" @click="refreshTasks">刷新提醒</el-button>
          </div>
        </div>
      </div>
    </div>

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <el-dialog :model-value="!!assigningTask" :title="`派发工单 ${assigningTask?.source_id ?? ''}`" width="min(90vw, 560px)" @close="closeAssignTask">
      <el-form label-position="top">
        <el-form-item label="负责人" required>
          <el-input v-model="assignee" placeholder="维修组-王工" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeAssignTask">取消</el-button>
        <el-button type="primary" :loading="!!assigningTask && actionId === assigningTask.id" @click="assignTask">确认派发</el-button>
      </template>
    </el-dialog>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
      <div
        v-for="card in summaryCards"
        :key="card.label"
        :class="[
          'rounded-2xl border p-5 shadow-sm',
          card.label === '匹配提醒' ? 'border-brand-900 bg-brand-900 text-white' : 'border-slate-200 bg-white',
        ]"
      >
        <p :class="['text-xs font-semibold uppercase tracking-[0.14em]', card.label === '匹配提醒' ? 'text-emerald-200' : 'text-slate-500']">{{ card.label }}</p>
        <p :class="['mt-3 text-3xl font-bold tabular', card.label === '匹配提醒' ? 'text-white' : card.tone]">{{ card.value }}</p>
        <p :class="['mt-2 text-xs', card.label === '匹配提醒' ? 'text-slate-300' : 'text-slate-500']">{{ card.hint }}</p>
      </div>
    </div>

    <div>
      <div class="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-950">重点提醒</h2>
          <p class="mt-1 text-sm text-slate-500">按风险和时间维度展示，同一事项可能出现在多个提醒视角中。</p>
        </div>
      </div>
      <div class="grid grid-cols-1 gap-5 md:grid-cols-2 2xl:grid-cols-4">
        <el-card v-for="group in reminderGroups" :key="group.title" shadow="never" :class="['rounded-2xl border-t-4', group.accent]">
          <template #header>
            <div class="flex items-start justify-between gap-3">
              <div>
                <h2 class="text-base font-bold text-slate-950">{{ group.title }}</h2>
                <p class="mt-1 text-xs text-slate-500">{{ group.description }}</p>
              </div>
              <el-tag effect="plain" round>{{ group.total }}</el-tag>
            </div>
          </template>
        <div v-if="group.items.length" class="space-y-3">
          <div v-for="item in group.items" :key="item.id" class="rounded-2xl border border-slate-100 bg-slate-50 p-3 transition hover:border-slate-200 hover:bg-white">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-slate-950">{{ item.title }}</p>
                <p class="mt-1 line-clamp-2 text-xs text-slate-500">{{ item.description }}</p>
              </div>
              <el-tag class="shrink-0" :type="severityType(item.severity)" effect="light" round>{{ severityLabel(item.severity) }}</el-tag>
            </div>
            <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span class="truncate">{{ sourceLabel(item.source) }} · {{ item.related_room ?? item.source_id }}</span>
              <span class="font-semibold tabular">{{ item.due_date ?? '无截止日期' }}</span>
            </div>
          </div>
        </div>
          <p v-else class="rounded-2xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">{{ group.empty }}</p>
        </el-card>
      </div>
    </div>

    <el-card shadow="never" class="rounded-2xl">
      <template #header>
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 class="text-lg font-bold text-slate-950">全部提醒</h2>
            <p class="mt-1 text-sm text-slate-500">按来源和风险筛选后的匹配事项列表，支持分页浏览和快速处理。</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <el-tag effect="plain" round>{{ total }} 项</el-tag>
            <el-tag v-if="sourceFilter !== 'all'" type="info" effect="light" round>{{ sourceLabel(sourceFilter) }}</el-tag>
            <el-tag v-if="severityFilter !== 'all'" :type="severityType(severityFilter)" effect="light" round>{{ severityLabel(severityFilter) }}</el-tag>
          </div>
        </div>
      </template>
      <div class="overflow-hidden rounded-2xl border border-slate-100">
        <div class="overflow-x-auto">
          <el-table v-loading="loading" class="min-w-[1120px]" :data="paginatedItems" empty-text="暂无提醒事项" row-key="id">
            <el-table-column label="事项" min-width="260">
              <template #default="{ row }">
                <p class="font-semibold text-slate-950">{{ row.title }}</p>
                <p class="mt-1 line-clamp-2 text-xs text-slate-500">{{ row.description }}</p>
              </template>
            </el-table-column>
            <el-table-column label="来源" min-width="90">
              <template #default="{ row }">
                <el-tag effect="plain" round>{{ sourceLabel(rowAsTodo(row).source) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关联对象" min-width="160">
              <template #default="{ row }">
                <p class="font-semibold">{{ row.related_room ?? '-' }}</p>
                <p class="text-xs text-slate-500">{{ row.related_person ?? row.source_id }}</p>
              </template>
            </el-table-column>
            <el-table-column label="截止日期" min-width="120">
              <template #default="{ row }">
                <span class="font-semibold tabular" :class="row.severity === 'danger' ? 'text-rose-700' : 'text-slate-700'">{{ row.due_date ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="负责人" min-width="120">
              <template #default="{ row }">{{ row.assignee ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" min-width="100">
              <template #default="{ row }">
                <StatusChip :status="row.status" />
                <span class="sr-only">{{ statusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="风险" min-width="100">
              <template #default="{ row }">
                <el-tag :type="severityType(rowAsTodo(row).severity)" effect="light" round>{{ severityLabel(rowAsTodo(row).severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="hasActions" label="操作" fixed="right" min-width="170">
              <template #default="{ row }">
                <div class="flex flex-wrap gap-2">
                  <el-button v-if="canApproveTask(rowAsTodo(row))" size="small" type="primary" :loading="actionId === row.id" @click="runTaskAction(rowAsTodo(row))">审批生效</el-button>
                  <el-button v-if="canAssignTask(rowAsTodo(row))" size="small" type="primary" plain :loading="actionId === row.id" @click="openAssignTask(rowAsTodo(row))">派单</el-button>
                  <el-button v-if="canResolveTask(rowAsTodo(row))" size="small" type="success" plain :loading="actionId === row.id" @click="runTaskAction(rowAsTodo(row))">完成</el-button>
                  <el-button v-if="canConfirmTask(rowAsTodo(row))" size="small" type="success" plain :loading="actionId === row.id" @click="runTaskAction(rowAsTodo(row))">确认已支付</el-button>
                  <el-button v-if="canRetryTask(rowAsTodo(row))" size="small" type="warning" plain :loading="actionId === row.id" @click="runTaskAction(rowAsTodo(row))">重试匹配</el-button>
                  <el-button v-if="canReviewTask(rowAsTodo(row))" size="small" type="warning" plain :loading="actionId === row.id" @click="runTaskAction(rowAsTodo(row))">标记已复核</el-button>
                  <span v-if="!hasRowAction(rowAsTodo(row))" class="text-xs text-slate-400">请到源模块处理</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <div class="mt-4 flex justify-center overflow-x-auto md:justify-end">
        <el-pagination
          :current-page="currentPage"
          :page-size="pageSize"
          :page-sizes="pageSizes"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </section>
</template>
