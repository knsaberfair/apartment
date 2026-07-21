<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElMessageBox, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import StatusChip from '@/components/ui/StatusChip.vue'
import Toolbar from '@/components/ui/Toolbar.vue'
import { useServerPagination } from '@/composables/useServerPagination'
import { usePermissions } from '@/composables/usePermissions'
import { pageActionPermissions } from '@/config/permissions'
import { ApiError, api, currency } from '@/services/api'
import type { Property, PropertyCreatePayload, PropertyStatus, PropertyUpdatePayload } from '@/types/domain'

interface PropertyForm {
  id: string
  building: string
  room: string
  layout: string
  area: number | null
  rent: number | null
  status: PropertyStatus
  tenant: string
  lease_end: string | null
  tagsText: string
}

const emptyForm = (): PropertyForm => ({
  id: '',
  building: '',
  room: '',
  layout: '',
  area: 0,
  rent: 0,
  status: 'vacant',
  tenant: '',
  lease_end: '',
  tagsText: '',
})

const statusOptions: Array<{ label: string; value: PropertyStatus }> = [
  { label: '已出租', value: 'occupied' },
  { label: '空置', value: 'vacant' },
  { label: '已预定', value: 'reserved' },
  { label: '维修中', value: 'maintenance' },
]

const { hasPermission } = usePermissions()
const properties = ref<Property[]>([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref<string | null>(null)
const showForm = ref(false)
const editingProperty = ref<Property | null>(null)
const form = ref<PropertyForm>(emptyForm())
const loadError = ref('')
const actionError = ref('')
const searchKeyword = ref('')
let propertiesRequestId = 0

const canCreate = computed(() => hasPermission(pageActionPermissions.propertyCreate))
const canUpdate = computed(() => hasPermission(pageActionPermissions.propertyUpdate))
const canDelete = computed(() => hasPermission(pageActionPermissions.propertyDelete))
const hasActions = computed(() => canUpdate.value || canDelete.value)
const { currentPage, pageSize, pageSizes, total, offset, resetPage, normalizeCurrentPage, handleSizeChange, handleCurrentChange } = useServerPagination()
const paginatedProperties = computed(() => properties.value)
const totalProperties = computed(() => total.value)
const occupiedProperties = computed(() => properties.value.filter((item) => item.status === 'occupied').length)
const vacantProperties = computed(() => properties.value.filter((item) => item.status === 'vacant').length)
const maintenanceProperties = computed(() => properties.value.filter((item) => item.status === 'maintenance').length)

function errorMessage(err: unknown, fallback: string) {
  if (err instanceof ApiError && typeof err.detail === 'object' && err.detail && 'detail' in err.detail) {
    const detail = err.detail.detail
    if (typeof detail === 'object' && detail && 'message' in detail && typeof detail.message === 'string') {
      return detail.message
    }
  }
  return err instanceof Error ? err.message : fallback
}

function normalizeTags(tagsText: string) {
  return tagsText
    .split(/[,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function normalizeOptional(value: string | null) {
  const normalized = value?.trim() ?? ''
  return normalized || null
}

function validateForm() {
  if (!editingProperty.value && !form.value.id.trim()) return '请输入房源编号'
  if (!form.value.building.trim()) return '请输入楼栋'
  if (!form.value.room.trim()) return '请输入房号'
  if (!form.value.layout.trim()) return '请输入户型'
  if (form.value.area === null || !Number.isFinite(form.value.area) || form.value.area <= 0) return '面积必须是有效正数'
  if (form.value.rent === null || form.value.rent < 0 || !Number.isInteger(form.value.rent)) return '月租金必须是非负整数'
  if (form.value.status === 'vacant' && (form.value.tenant.trim() || form.value.lease_end)) return '空置房源不能填写租客或租约结束日'
  if ((form.value.status === 'occupied' || form.value.status === 'reserved') && (!form.value.tenant.trim() || !form.value.lease_end)) return '已出租或已预定房源必须填写租客和租约结束日'
  return ''
}

function buildUpdatePayload(): PropertyUpdatePayload {
  return {
    building: form.value.building.trim(),
    room: form.value.room.trim(),
    layout: form.value.layout.trim(),
    area: Number(form.value.area),
    rent: Number(form.value.rent),
    status: form.value.status,
    tenant: normalizeOptional(form.value.tenant),
    lease_end: normalizeOptional(form.value.lease_end),
    tags: normalizeTags(form.value.tagsText),
  }
}

function buildCreatePayload(): PropertyCreatePayload {
  return {
    id: form.value.id.trim(),
    ...buildUpdatePayload(),
  }
}

async function loadProperties() {
  const requestId = ++propertiesRequestId
  loading.value = true
  loadError.value = ''
  try {
    const requestedPage = currentPage.value
    const response = await api.properties({ limit: pageSize.value, offset: offset.value, q: searchKeyword.value.trim() || undefined })
    if (requestId !== propertiesRequestId) return
    total.value = response.total
    if (!response.items.length && response.total > 0 && requestedPage > 1) {
      normalizeCurrentPage()
      return
    }
    properties.value = response.items
    normalizeCurrentPage()
  } catch (err) {
    if (requestId === propertiesRequestId) {
      loadError.value = errorMessage(err, '房源加载失败')
    }
  } finally {
    if (requestId === propertiesRequestId) {
      loading.value = false
    }
  }
}

function openCreateForm() {
  if (!canCreate.value) return
  editingProperty.value = null
  form.value = emptyForm()
  actionError.value = ''
  showForm.value = true
}

function asProperty(row: unknown): Property {
  return row as Property
}

function openEditForm(property: Property) {
  if (!canUpdate.value) return
  editingProperty.value = property
  form.value = {
    id: property.id,
    building: property.building,
    room: property.room,
    layout: property.layout,
    area: property.area,
    rent: property.rent,
    status: property.status,
    tenant: property.tenant ?? '',
    lease_end: property.lease_end ?? '',
    tagsText: property.tags.join('，'),
  }
  actionError.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingProperty.value = null
  form.value = emptyForm()
  actionError.value = ''
}

async function saveProperty() {
  if (editingProperty.value) {
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
    if (editingProperty.value) {
      await api.updateProperty(editingProperty.value.id, buildUpdatePayload())
      ElMessage.success('房源已更新')
    } else {
      await api.createProperty(buildCreatePayload())
      ElMessage.success('房源已新增')
    }
    closeForm()
    await loadProperties()
  } catch (err) {
    actionError.value = errorMessage(err, '保存房源失败')
  } finally {
    saving.value = false
  }
}

async function deleteProperty(property: Property) {
  if (!canDelete.value) return

  try {
    await ElMessageBox.confirm(`确认删除房源 ${property.building}-${property.room}（${property.id}）吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }

  deletingId.value = property.id
  actionError.value = ''
  try {
    await api.deleteProperty(property.id)
    ElMessage.success('房源已删除')
    await loadProperties()
  } catch (err) {
    actionError.value = errorMessage(err, '删除房源失败')
  } finally {
    deletingId.value = null
  }
}

watch(searchKeyword, () => {
  if (currentPage.value === 1) {
    void loadProperties()
  } else {
    resetPage()
  }
})

watch([currentPage, pageSize], () => {
  void loadProperties()
})

onMounted(loadProperties)
</script>

<template>
  <section class="space-y-6">
    <Toolbar v-model="searchKeyword" title="房源管理" description="集中管理楼栋、房间、租金、出租状态与房源标签，支持运营人员快速判断可租资源。" action-label="新增房源" search-placeholder="搜索房源、楼栋、租客或标签" :action-permission="pageActionPermissions.propertyCreate" @action="openCreateForm" />

    <el-alert v-if="loadError || actionError" :title="loadError || actionError" type="error" show-icon :closable="false" />

    <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">匹配房源</p><p class="mt-3 text-3xl font-bold tabular">{{ totalProperties }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页已出租</p><p class="mt-3 text-3xl font-bold text-emerald-600 tabular">{{ occupiedProperties }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页空置</p><p class="mt-3 text-3xl font-bold text-amber-600 tabular">{{ vacantProperties }}</p></el-card>
      <el-card shadow="never" class="rounded-2xl"><p class="eyebrow">本页维修中</p><p class="mt-3 text-3xl font-bold text-rose-600 tabular">{{ maintenanceProperties }}</p></el-card>
    </div>

    <el-dialog v-model="showForm" :title="editingProperty ? '编辑房源' : '新增房源'" width="min(90vw, 720px)" @close="closeForm">
      <p class="mb-5 text-sm text-slate-500">填写房源基础信息，保存后将同步到 SQLite 数据库。</p>
      <el-form label-position="top" :model="form">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <el-form-item label="房源编号" required>
            <el-input v-model="form.id" :disabled="!!editingProperty" placeholder="P-2201" />
          </el-form-item>
          <el-form-item label="楼栋" required>
            <el-input v-model="form.building" placeholder="A 栋" />
          </el-form-item>
          <el-form-item label="房号" required>
            <el-input v-model="form.room" placeholder="1201" />
          </el-form-item>
          <el-form-item label="户型" required>
            <el-input v-model="form.layout" placeholder="两室一厅" />
          </el-form-item>
          <el-form-item label="面积（㎡）" required>
            <el-input-number v-model="form.area" :min="0" :step="0.1" class="w-full" />
          </el-form-item>
          <el-form-item label="月租金" required>
            <el-input-number v-model="form.rent" :min="0" :step="100" :precision="0" class="w-full" />
          </el-form-item>
          <el-form-item label="状态" required>
            <el-select v-model="form.status" class="w-full">
              <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="当前租客">
            <el-input v-model="form.tenant" placeholder="空置可不填" />
          </el-form-item>
          <el-form-item label="租约结束日">
            <el-date-picker v-model="form.lease_end" class="w-full" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item class="md:col-span-3" label="标签">
            <el-input v-model="form.tagsText" placeholder="多个标签用逗号分隔，例如：南向，近地铁" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="closeForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProperty">保存房源</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" class="rounded-2xl">
      <div class="overflow-x-auto">
        <el-table v-loading="loading" class="min-w-[1050px]" :data="paginatedProperties" empty-text="暂无房源数据" row-key="id">
        <el-table-column prop="id" label="房源编号" min-width="110" />
        <el-table-column label="楼栋/房号" min-width="130">
          <template #default="{ row }">
            <span class="font-semibold text-slate-950">{{ row.building }}-{{ row.room }}</span>
          </template>
        </el-table-column>
        <el-table-column label="户型面积" min-width="150">
          <template #default="{ row }">{{ row.layout }} · {{ row.area }}㎡</template>
        </el-table-column>
        <el-table-column label="月租金" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold tabular">{{ currency(row.rent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="当前租客" min-width="120">
          <template #default="{ row }">{{ row.tenant ?? '待出租' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusChip :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1.5">
              <el-tag v-for="tag in row.tags" :key="tag" type="info" effect="plain">{{ tag }}</el-tag>
              <span v-if="!row.tags.length" class="text-xs text-slate-400">无标签</span>
            </div>
          </template>
        </el-table-column>
          <el-table-column v-if="hasActions" label="操作" width="150">
          <template #default="{ row }">
            <div class="flex gap-2">
              <el-button v-if="canUpdate" size="small" @click="openEditForm(asProperty(row))">编辑</el-button>
              <el-button v-if="canDelete" size="small" type="danger" plain :loading="deletingId === row.id" @click="deleteProperty(asProperty(row))">删除</el-button>
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
