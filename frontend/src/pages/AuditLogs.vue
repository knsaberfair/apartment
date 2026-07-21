<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElCard, ElDatePicker, ElForm, ElFormItem, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import Toolbar from '@/components/ui/Toolbar.vue'
import { ApiError, api } from '@/services/api'
import type { AuditLog } from '@/types/domain'

const logs = ref<AuditLog[]>([])
const loading = ref(false)
const loadError = ref('')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)
const pageSizes = [10, 20, 50, 100]
const actionFilter = ref('')
const resourceTypeFilter = ref('')
const actorRoleFilter = ref('')
const timeRange = ref<[string, string] | null>(null)
let auditLogsRequestId = 0

const actionLabels: Record<string, string> = {
  approve: '审批',
  assign: '派发',
  confirm: '确认',
  create: '新建',
  delete: '删除',
  generate: '生成',
  import: '导入',
  move_out: '退租',
  renew: '续签',
  resolve: '复核',
  retry: '重试',
  settle: '结算',
  terminate: '终止',
  update: '更新',
  update_permissions: '更新权限',
}

const resourceLabels: Record<string, string> = {
  contract: '合同',
  deposit_settlement: '押金结算',
  finance_transaction: '财务流水',
  maintenance_order: '维修工单',
  move_out: '退租记录',
  permission_resource: '权限资源',
  property: '房源',
  reconciliation: '对账记录',
  rent_bill: '租金账单',
  role: '角色',
  tenant: '租客',
}

const roleLabels: Record<string, string> = {
  admin: '管理员',
  manager: '经理',
  super_admin: '超级管理员',
}

const actionOptions = computed(() => Object.entries(actionLabels).map(([value, label]) => ({ value, label })))
const resourceOptions = computed(() => Object.entries(resourceLabels).map(([value, label]) => ({ value, label })))
const roleOptions = computed(() => Object.entries(roleLabels).map(([value, label]) => ({ value, label })))
const actorCount = computed(() => new Set(logs.value.map((item) => item.actor_id)).size)
const resourceCount = computed(() => new Set(logs.value.map((item) => item.resource_type)).size)
const offset = computed(() => (currentPage.value - 1) * pageSize.value)

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

function actionLabel(action: string) {
  return actionLabels[action] ?? action
}

function resourceLabel(resource: string) {
  return resourceLabels[resource] ?? resource
}

function roleLabel(role: string) {
  return roleLabels[role] ?? role
}

async function loadAuditLogs() {
  const requestId = ++auditLogsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.auditLogs({
      limit: pageSize.value,
      offset: offset.value,
      q: searchKeyword.value.trim() || undefined,
      action: actionFilter.value || undefined,
      resource_type: resourceTypeFilter.value || undefined,
      actor_role: actorRoleFilter.value || undefined,
      created_from: timeRange.value?.[0],
      created_to: timeRange.value?.[1],
    })
    if (requestId !== auditLogsRequestId) return
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      currentPage.value = Math.ceil(response.total / pageSize.value)
      return
    }
    logs.value = response.items
  } catch (err) {
    if (requestId === auditLogsRequestId) {
      loadError.value = errorMessage(err, '审计日志加载失败')
    }
  } finally {
    if (requestId === auditLogsRequestId) {
      loading.value = false
    }
  }
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  void loadAuditLogs()
}

function handleCurrentChange(page: number) {
  currentPage.value = page
  void loadAuditLogs()
}

function resetAndLoad() {
  currentPage.value = 1
  void loadAuditLogs()
}

watch([searchKeyword, actionFilter, resourceTypeFilter, actorRoleFilter, timeRange], resetAndLoad)

onMounted(() => {
  void loadAuditLogs()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="操作审计" description="集中查看合同、财务、权限等关键业务动作的操作留痕，便于追溯责任人与资源变更。" search-placeholder="搜索操作人、动作、资源或时间" />

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <div class="grid grid-cols-1 gap-5 md:grid-cols-3">
      <el-card shadow="never" class="rounded-2xl">
        <p class="eyebrow">Audit Events</p>
        <p class="mt-3 text-3xl font-bold text-slate-950 tabular">{{ total }}</p>
        <p class="mt-1 text-sm text-slate-500">匹配日志总数</p>
      </el-card>
      <el-card shadow="never" class="rounded-2xl">
        <p class="eyebrow">本页 Actors</p>
        <p class="mt-3 text-3xl font-bold text-emerald-700 tabular">{{ actorCount }}</p>
        <p class="mt-1 text-sm text-slate-500">当前页涉及操作人</p>
      </el-card>
      <el-card shadow="never" class="rounded-2xl">
        <p class="eyebrow">本页 Resources</p>
        <p class="mt-3 text-3xl font-bold text-brand-700 tabular">{{ resourceCount }}</p>
        <p class="mt-1 text-sm text-slate-500">当前页资源类型</p>
      </el-card>
    </div>

    <el-card shadow="never" class="rounded-2xl">
      <el-form class="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-4" label-position="top">
        <el-form-item label="动作">
          <el-select v-model="actionFilter" data-testid="audit-action-filter" clearable placeholder="全部动作">
            <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="resourceTypeFilter" data-testid="audit-resource-filter" clearable placeholder="全部资源">
            <el-option v-for="item in resourceOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="actorRoleFilter" data-testid="audit-role-filter" clearable placeholder="全部角色">
            <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="发生时间">
          <el-date-picker v-model="timeRange" class="!w-full" data-testid="audit-time-filter" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ssZ" start-placeholder="开始时间" end-placeholder="结束时间" />
        </el-form-item>
      </el-form>

      <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-sm text-slate-500">第 {{ currentPage }} 页，当前显示 {{ logs.length }} 条 / 共 {{ total }} 条</p>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="pageSizes"
          :total="total"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[980px]" :data="logs" empty-text="暂无审计日志" row-key="id">
          <el-table-column prop="id" label="编号" width="90">
            <template #default="{ row }">
              <span class="font-semibold text-slate-950 tabular">#{{ row.id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作人" min-width="160">
            <template #default="{ row }">
              <p class="font-semibold text-slate-950">{{ row.actor_name }}</p>
              <p class="text-xs text-slate-500">{{ row.actor_id }} · {{ roleLabel(row.actor_role) }}</p>
            </template>
          </el-table-column>
          <el-table-column label="动作" min-width="130">
            <template #default="{ row }">
              <el-tag type="primary" effect="plain" round>{{ actionLabel(row.action) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="资源" min-width="180">
            <template #default="{ row }">
              <p class="font-semibold">{{ resourceLabel(row.resource_type) }}</p>
              <p class="text-xs text-slate-500">{{ row.resource_id }}</p>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="发生时间" min-width="180" />
        </el-table>
      </div>
    </el-card>
  </section>
</template>
