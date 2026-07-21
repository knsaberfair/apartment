<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElMessage, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { pageActionPermissions } from '@/config/permissions'
import { ApiError, api } from '@/services/api'
import type { MaintenanceOrder, MaintenanceOrderCreatePayload, MaintenancePriority, PropertyOption } from '@/types/domain'

interface OrderForm {
  id: string
  property_id: string
  title: string
  tenant: string
  category: string
  priority: MaintenancePriority
  due_at: string | null
}

const emptyForm = (): OrderForm => ({
  id: '',
  property_id: '',
  title: '',
  tenant: '',
  category: '',
  priority: 'medium',
  due_at: '',
})

const priorityOptions: Array<{ label: string; value: MaintenancePriority }> = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' },
]

const { hasPermission } = usePermissions()
const orders = ref<MaintenanceOrder[]>([])
const properties = ref<PropertyOption[]>([])
const propertiesLoaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const actionId = ref<string | null>(null)
const showForm = ref(false)
const assigningOrder = ref<MaintenanceOrder | null>(null)
const assignee = ref('')
const form = ref<OrderForm>(emptyForm())
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let ordersRequestId = 0

const canCreate = computed(() => hasPermission(pageActionPermissions.maintenanceCreate))
const canAssign = computed(() => hasPermission(pageActionPermissions.maintenanceAssign))
const canResolve = computed(() => hasPermission(pageActionPermissions.maintenanceResolve))
const hasActions = computed(() => canAssign.value || canResolve.value)
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedOrders = computed(() => orders.value)
const openOrders = computed(() => orders.value.filter((order) => order.status === 'open').length)
const inProgressOrders = computed(() => orders.value.filter((order) => order.status === 'in_progress').length)
const urgentOrders = computed(() => orders.value.filter((order) => order.priority === 'urgent' && order.status !== 'resolved').length)
const resolvedOrders = computed(() => orders.value.filter((order) => order.status === 'resolved').length)

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
  if (!form.value.id.trim()) return '请输入工单编号'
  if (!form.value.property_id) return '请选择房源'
  if (!form.value.title.trim()) return '请输入问题描述'
  if (!form.value.tenant.trim()) return '请输入报修人'
  if (!form.value.category.trim()) return '请输入分类'
  if (!form.value.due_at) return '请选择截止日期'
  return ''
}

function buildCreatePayload(): MaintenanceOrderCreatePayload {
  return {
    id: form.value.id.trim(),
    property_id: form.value.property_id,
    title: form.value.title.trim(),
    tenant: form.value.tenant.trim(),
    category: form.value.category.trim(),
    priority: form.value.priority,
    due_at: form.value.due_at ?? '',
  }
}

async function loadOrders() {
  const requestId = ++ordersRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.maintenanceOrders({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== ordersRequestId) return false
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return true
    }
    orders.value = response.items
    normalizeCurrentPage()
    return true
  } catch (err) {
    if (requestId === ordersRequestId) {
      loadError.value = errorMessage(err, '工单加载失败')
    }
    return false
  } finally {
    if (requestId === ordersRequestId) {
      loading.value = false
    }
  }
}

async function loadProperties() {
  try {
    properties.value = await api.maintenancePropertyOptions()
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

async function saveOrder() {
  if (!canCreate.value) return
  const validationError = validateForm()
  if (validationError) {
    actionError.value = validationError
    return
  }

  saving.value = true
  actionError.value = ''
  try {
    await api.createMaintenanceOrder(buildCreatePayload())
    notifyTasksUpdated()
    closeForm()
    const [ordersLoaded, propertiesRefreshed] = await Promise.all([loadOrders(), loadProperties()])
    if (!ordersLoaded || !propertiesRefreshed) {
      actionError.value = '工单已创建，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('工单已创建')
  } catch (err) {
    actionError.value = errorMessage(err, '创建工单失败')
  } finally {
    saving.value = false
  }
}

function openAssignForm(order: MaintenanceOrder) {
  if (!canAssign.value || order.status !== 'open') return
  assigningOrder.value = order
  assignee.value = order.assignee === '未分配' ? '' : order.assignee
  actionError.value = ''
}

function closeAssignForm() {
  assigningOrder.value = null
  assignee.value = ''
  actionError.value = ''
}

async function assignOrder() {
  if (!canAssign.value || !assigningOrder.value) return
  if (!assignee.value.trim()) {
    actionError.value = '请输入负责人'
    return
  }

  actionId.value = assigningOrder.value.id
  actionError.value = ''
  try {
    await api.assignMaintenanceOrder(assigningOrder.value.id, { assignee: assignee.value.trim() })
    notifyTasksUpdated()
    closeAssignForm()
    if (!(await loadOrders())) {
      actionError.value = '工单已派发，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('工单已派发')
  } catch (err) {
    actionError.value = errorMessage(err, '派发工单失败')
  } finally {
    actionId.value = null
  }
}

async function resolveOrder(order: MaintenanceOrder) {
  if (!canResolve.value || order.status !== 'in_progress') return
  actionId.value = order.id
  actionError.value = ''
  try {
    await api.resolveMaintenanceOrder(order.id)
    notifyTasksUpdated()
    if (assigningOrder.value?.id === order.id) {
      closeAssignForm()
    }
    if (!(await loadOrders())) {
      actionError.value = '工单已完成，但数据刷新失败，请手动刷新页面'
      return
    }
    ElMessage.success('工单已完成')
  } catch (err) {
    actionError.value = errorMessage(err, '完成工单失败')
  } finally {
    actionId.value = null
  }
}

function asOrder(row: unknown): MaintenanceOrder {
  return row as MaintenanceOrder
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadOrders()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadOrders()
})

onMounted(() => {
  void loadOrders()
})
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="工单维修" description="统一管理租客报修、派单、维修进度与验收结果，保障居住体验和响应效率。" action-label="创建工单" search-placeholder="搜索工单、房间、报修人或负责人" :action-permission="pageActionPermissions.maintenanceCreate" @action="openCreateForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <el-dialog v-model="showForm" title="创建维修工单" width="720px" @close="closeForm">
      <el-form label-position="top" :model="form">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <el-form-item label="工单编号" required>
            <el-input v-model="form.id" placeholder="M-20260715-01" />
          </el-form-item>
          <el-form-item label="关联房源" required>
            <el-select v-model="form.property_id" class="w-full" filterable placeholder="请选择房源">
              <el-option v-for="property in properties" :key="property.id" :label="`${property.building}-${property.room}（${property.id}）`" :value="property.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="报修人" required>
            <el-input v-model="form.tenant" placeholder="租客/客服" />
          </el-form-item>
          <el-form-item label="问题描述" required>
            <el-input v-model="form.title" placeholder="例如：空调制冷异常" />
          </el-form-item>
          <el-form-item label="分类" required>
            <el-input v-model="form.category" placeholder="家电/管道/装修" />
          </el-form-item>
          <el-form-item label="优先级" required>
            <el-select v-model="form.priority" class="w-full">
              <el-option v-for="option in priorityOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="截止日期" required>
            <el-date-picker v-model="form.due_at" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveOrder">保存工单</el-button>
      </template>
    </el-dialog>

    <el-dialog :model-value="!!assigningOrder" :title="assigningOrder ? `派发工单 ${assigningOrder.id}` : '派发工单'" width="480px" @close="closeAssignForm">
      <el-form label-position="top">
        <el-form-item label="负责人" required>
          <el-input v-model="assignee" placeholder="维修组-王工" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeAssignForm">取消</el-button>
        <el-button type="primary" :loading="actionId === assigningOrder?.id" @click="assignOrder">确认派发</el-button>
      </template>
    </el-dialog>

    <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页未派单</p><p class="mt-3 text-3xl font-bold text-blue-700 tabular">{{ openOrders }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页处理中</p><p class="mt-3 text-3xl font-bold text-amber-700 tabular">{{ inProgressOrders }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页高优先级</p><p class="mt-3 text-3xl font-bold text-violet-700 tabular">{{ urgentOrders }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页已完成</p><p class="mt-3 text-3xl font-bold text-emerald-700 tabular">{{ resolvedOrders }}</p></el-card>
    </div>

    <el-card shadow="never" class="rounded-2xl">
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[1120px]" :data="paginatedOrders" empty-text="暂无工单数据" row-key="id">
        <el-table-column prop="id" label="工单编号" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-slate-950">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="问题描述" min-width="190">
          <template #default="{ row }">
            <p class="font-semibold">{{ row.title }}</p>
            <p class="text-xs text-slate-500">创建 {{ row.created_at }}</p>
          </template>
        </el-table-column>
        <el-table-column label="房间/租客" min-width="150">
          <template #default="{ row }">
            <p class="font-semibold">{{ row.room }}</p>
            <p class="text-xs text-slate-500">{{ row.tenant }}</p>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" min-width="110" />
        <el-table-column label="优先级" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.priority" />
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="assignee" label="负责人" min-width="110" />
        <el-table-column prop="due_at" label="截止时间" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-slate-700">{{ row.due_at }}</span>
          </template>
        </el-table-column>
          <el-table-column v-if="hasActions" label="操作" width="170">
          <template #default="{ row }">
            <div class="flex gap-2">
              <el-button v-if="canAssign && row.status === 'open'" size="small" @click="openAssignForm(asOrder(row))">派发</el-button>
              <el-button v-if="canResolve && row.status === 'in_progress'" size="small" type="success" plain :loading="actionId === row.id" @click="resolveOrder(asOrder(row))">完成</el-button>
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
