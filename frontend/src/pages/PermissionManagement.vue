<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElAlert, ElButton, ElCard, ElCheckbox, ElDialog, ElInput, ElMessageBox, ElOption, ElSelect } from 'element-plus'
import { Plus, Save, ShieldCheck } from '@lucide/vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api } from '@/services/api'
import type { CreatePermissionResourcePayload, PermissionGroup, PermissionKey, PermissionResource, PermissionResourceType, RoleDefinition, RoleKey } from '@/types/auth'

const catalog = ref<PermissionGroup[]>([])
const permissionResources = ref<PermissionResource[]>([])
const roleDefinitions = ref<RoleDefinition[]>([])
const selectedRole = ref<RoleKey>('manager')
const draftPermissions = ref<Set<PermissionKey>>(new Set())
const loading = ref(true)
const saving = ref(false)
const creating = ref(false)
const creatingResource = ref(false)
const updatingRole = ref(false)
const deletingRole = ref(false)
const deletingResource = ref<PermissionKey | ''>('')
const showCreateRoleForm = ref(false)
const showCreateResourceForm = ref(false)
const editingRole = ref(false)
const editingResourceKey = ref<PermissionKey | ''>('')
const newRoleKey = ref('')
const newRoleLabel = ref('')
const editingRoleLabel = ref('')
const roleSearch = ref('')
const permissionSearch = ref('')
const resourceType = ref<PermissionResourceType>('menu')
const resourceKey = ref('')
const resourceLabel = ref('')
const resourceDescription = ref('')
const resourceGroup = ref('')
const resourceGroupLabel = ref('')
const resourceRoute = ref('')
const resourceMenuLabel = ref('')
const resourceMenuHint = ref('')
const resourceSort = ref<number | null>(null)
const message = ref('')
const loadError = ref('')
const actionError = ref('')

const { currentRole, hasPermission, loadCurrentUser, refreshPermissionResources, refreshRoles } = usePermissions()
const canManagePermissions = computed(() => hasPermission(pageActionPermissions.permissionManage))
const selectedRoleDefinition = computed(() => roleDefinitions.value.find((role) => role.key === selectedRole.value) ?? null)
const selectedRolePermissionsAreEditable = computed(() => Boolean(canManagePermissions.value && selectedRoleDefinition.value))
const selectedRoleIsEditable = computed(() => Boolean(selectedRolePermissionsAreEditable.value && !selectedRoleDefinition.value?.built_in))
const allPermissionCount = computed(() => catalog.value.reduce((count, group) => count + group.permissions.length, 0))
const selectedCount = computed(() => draftPermissions.value.size)
const isDirty = computed(() => {
  const original = new Set(selectedRoleDefinition.value?.permissions ?? [])
  if (original.size !== draftPermissions.value.size) return true
  return Array.from(draftPermissions.value).some((permission) => !original.has(permission))
})
const roleKeyPattern = /^[a-z][a-z0-9_]{2,31}$/
const permissionKeyPattern = /^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$/
const customRoutePattern = /^\/custom\/[a-z][a-z0-9_-]{1,63}$/
const canCreateRole = computed(() => canManagePermissions.value && roleKeyPattern.test(newRoleKey.value) && newRoleLabel.value.trim().length > 0)
const canSavePermissions = computed(() => selectedRolePermissionsAreEditable.value && isDirty.value && !saving.value)
const canSubmitResource = computed(() => {
  const keyValid = editingResourceKey.value || permissionKeyPattern.test(resourceKey.value)
  const baseValid =
    canManagePermissions.value &&
    keyValid &&
    resourceLabel.value.trim().length > 0 &&
    resourceDescription.value.trim().length > 0 &&
    resourceGroup.value.trim().length > 0 &&
    resourceGroupLabel.value.trim().length > 0

  if (!baseValid) return false
  if (resourceType.value !== 'menu') return true
  return customRoutePattern.test(resourceRoute.value) && resourceMenuLabel.value.trim().length > 0
})
const filteredRoles = computed(() => {
  const keyword = roleSearch.value.trim().toLowerCase()
  if (!keyword) return roleDefinitions.value
  return roleDefinitions.value.filter((role) => role.key.toLowerCase().includes(keyword) || role.label.toLowerCase().includes(keyword))
})
const filteredCatalog = computed(() => {
  const keyword = permissionSearch.value.trim().toLowerCase()
  if (!keyword) return catalog.value
  return catalog.value
    .map((group) => ({
      ...group,
      permissions: group.permissions.filter(
        (permission) =>
          permission.key.toLowerCase().includes(keyword) ||
          permission.label.toLowerCase().includes(keyword) ||
          permission.description.toLowerCase().includes(keyword),
      ),
    }))
    .filter((group) => group.permissions.length > 0)
})
const roleFormDirty = computed(() => Boolean(newRoleKey.value.trim() || newRoleLabel.value.trim()))
const resourceFormDirty = computed(() =>
  Boolean(
    resourceKey.value.trim() ||
      resourceLabel.value.trim() ||
      resourceDescription.value.trim() ||
      resourceGroup.value.trim() ||
      resourceGroupLabel.value.trim() ||
      resourceRoute.value.trim() ||
      resourceMenuLabel.value.trim() ||
      resourceMenuHint.value.trim() ||
      resourceSort.value,
  ),
)

const defaultNewRolePermissions: PermissionKey[] = ['dashboard:view']

function resetDraft(role: RoleDefinition | null) {
  draftPermissions.value = new Set(role?.permissions ?? [])
}

async function confirmDiscardChanges() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前角色权限尚未保存，继续操作将丢弃更改。', '未保存更改', { confirmButtonText: '丢弃更改', cancelButtonText: '取消', type: 'warning' })
    return true
  } catch {
    return false
  }
}

async function confirmCloseForm(dirty: boolean) {
  if (!dirty) return true
  try {
    await ElMessageBox.confirm('表单内容尚未保存，确认关闭？', '关闭表单', { confirmButtonText: '关闭', cancelButtonText: '取消', type: 'warning' })
    return true
  } catch {
    return false
  }
}

async function selectRole(role: RoleDefinition) {
  if (role.key === selectedRole.value) return
  if (!(await confirmDiscardChanges())) return
  selectedRole.value = role.key
  resetDraft(role)
  editingRole.value = false
  editingRoleLabel.value = ''
  message.value = ''
  actionError.value = ''
}

function resetResourceForm() {
  editingResourceKey.value = ''
  resourceType.value = 'menu'
  resourceKey.value = ''
  resourceLabel.value = ''
  resourceDescription.value = ''
  resourceGroup.value = ''
  resourceGroupLabel.value = ''
  resourceRoute.value = ''
  resourceMenuLabel.value = ''
  resourceMenuHint.value = ''
  resourceSort.value = null
}

async function openCreateRoleForm() {
  if (!(await confirmDiscardChanges())) return
  showCreateRoleForm.value = true
  showCreateResourceForm.value = false
  newRoleKey.value = ''
  newRoleLabel.value = ''
  message.value = ''
  actionError.value = ''
}

async function closeCreateRoleForm() {
  if (!(await confirmCloseForm(roleFormDirty.value))) return
  showCreateRoleForm.value = false
  newRoleKey.value = ''
  newRoleLabel.value = ''
}

async function openCreateResourceForm() {
  if (!(await confirmDiscardChanges())) return
  showCreateResourceForm.value = true
  showCreateRoleForm.value = false
  resetResourceForm()
  message.value = ''
  actionError.value = ''
}

async function closeResourceForm() {
  if (!(await confirmCloseForm(resourceFormDirty.value))) return
  showCreateResourceForm.value = false
  resetResourceForm()
}

function permissionResourceByKey(key: PermissionKey) {
  return permissionResources.value.find((resource) => resource.key === key)
}

async function openEditResourceForm(key: PermissionKey) {
  const resource = permissionResourceByKey(key)
  if (!resource || resource.built_in || !(await confirmDiscardChanges())) return
  showCreateResourceForm.value = true
  showCreateRoleForm.value = false
  editingResourceKey.value = resource.key
  resourceType.value = resource.type
  resourceKey.value = resource.key
  resourceLabel.value = resource.label
  resourceDescription.value = resource.description
  resourceGroup.value = resource.group
  resourceGroupLabel.value = resource.group_label
  resourceRoute.value = resource.route ?? ''
  resourceMenuLabel.value = resource.menu_label ?? ''
  resourceMenuHint.value = resource.menu_hint ?? ''
  resourceSort.value = resource.sort ?? null
  message.value = ''
  actionError.value = ''
}

function isChecked(permission: PermissionKey) {
  return draftPermissions.value.has(permission)
}

function togglePermission(permission: PermissionKey) {
  if (!selectedRolePermissionsAreEditable.value) return

  const next = new Set(draftPermissions.value)
  if (next.has(permission)) {
    next.delete(permission)
  } else {
    next.add(permission)
  }
  draftPermissions.value = next
}

function extractApiMessage(err: unknown, fallback: string) {
  if (err instanceof ApiError && typeof err.detail === 'object' && err.detail && 'detail' in err.detail) {
    const detail = err.detail.detail
    if (typeof detail === 'object' && detail && 'message' in detail && typeof detail.message === 'string') {
      return detail.message
    }
  }
  return err instanceof Error ? err.message : fallback
}

async function loadPermissionData() {
  loading.value = true
  loadError.value = ''
  try {
    const [catalogResponse, rolesResponse, resourceResponse] = await Promise.all([api.permissionCatalog(), api.permissionRoles(), api.permissionResources()])
    catalog.value = catalogResponse
    roleDefinitions.value = rolesResponse
    permissionResources.value = resourceResponse
    const preferredRole = rolesResponse.find((role) => role.key === selectedRole.value) ?? rolesResponse[0]
    if (preferredRole) {
      selectedRole.value = preferredRole.key
      resetDraft(preferredRole)
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : '加载权限配置失败'
  } finally {
    loading.value = false
  }
}

async function reloadCatalogAndResources() {
  const [catalogResponse, resourceResponse] = await Promise.all([api.permissionCatalog(), api.permissionResources()])
  catalog.value = catalogResponse
  permissionResources.value = resourceResponse
  await refreshPermissionResources()
}

async function createRole() {
  if (!canCreateRole.value) return

  creating.value = true
  message.value = ''
  actionError.value = ''
  try {
    const createdRole = await api.createRole({
      key: newRoleKey.value.trim(),
      label: newRoleLabel.value.trim(),
      permissions: defaultNewRolePermissions,
    })
    roleDefinitions.value = [...roleDefinitions.value, createdRole]
    await refreshRoles()
    selectedRole.value = createdRole.key
    resetDraft(createdRole)
    showCreateRoleForm.value = false
    newRoleKey.value = ''
    newRoleLabel.value = ''
    message.value = `已创建角色 ${createdRole.label}，可继续勾选权限并保存`
  } catch (err) {
    actionError.value = extractApiMessage(err, '创建角色失败')
  } finally {
    creating.value = false
  }
}

function startEditRole() {
  if (!selectedRoleIsEditable.value || !selectedRoleDefinition.value) return
  editingRole.value = true
  editingRoleLabel.value = selectedRoleDefinition.value.label
  message.value = ''
  actionError.value = ''
}

function cancelEditRole() {
  editingRole.value = false
  editingRoleLabel.value = ''
}

async function updateSelectedRole() {
  if (!selectedRoleIsEditable.value || !editingRoleLabel.value.trim()) return
  updatingRole.value = true
  message.value = ''
  actionError.value = ''
  try {
    const updatedRole = await api.updateRole(selectedRole.value, { label: editingRoleLabel.value.trim() })
    roleDefinitions.value = roleDefinitions.value.map((role) => (role.key === updatedRole.key ? updatedRole : role))
    await refreshRoles()
    editingRole.value = false
    editingRoleLabel.value = ''
    message.value = `已更新角色 ${updatedRole.label}`
  } catch (err) {
    actionError.value = extractApiMessage(err, '更新角色失败')
  } finally {
    updatingRole.value = false
  }
}

async function deleteSelectedRole() {
  if (!selectedRoleIsEditable.value || !selectedRoleDefinition.value) return
  try {
    await ElMessageBox.confirm(`确认删除角色“${selectedRoleDefinition.value.label}”？`, '删除角色', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
  } catch {
    return
  }

  deletingRole.value = true
  message.value = ''
  actionError.value = ''
  try {
    await api.deleteRole(selectedRole.value)
    const remainingRoles = roleDefinitions.value.filter((role) => role.key !== selectedRole.value)
    roleDefinitions.value = remainingRoles
    await refreshRoles()
    const nextRole = remainingRoles[0] ?? null
    selectedRole.value = nextRole?.key ?? 'manager'
    resetDraft(nextRole)
    editingRole.value = false
    message.value = '角色已删除'
  } catch (err) {
    actionError.value = extractApiMessage(err, '删除角色失败')
  } finally {
    deletingRole.value = false
  }
}

function buildResourcePayload(): CreatePermissionResourcePayload {
  return {
    key: editingResourceKey.value || resourceKey.value.trim(),
    label: resourceLabel.value.trim(),
    description: resourceDescription.value.trim(),
    group: resourceGroup.value.trim(),
    group_label: resourceGroupLabel.value.trim(),
    type: resourceType.value,
    route: resourceType.value === 'menu' ? resourceRoute.value.trim() : null,
    menu_label: resourceType.value === 'menu' ? resourceMenuLabel.value.trim() : null,
    menu_hint: resourceType.value === 'menu' ? resourceMenuHint.value.trim() : null,
    sort: resourceSort.value,
  }
}

async function submitResource() {
  if (!canSubmitResource.value) return

  creatingResource.value = true
  message.value = ''
  actionError.value = ''
  try {
    const wasEditing = Boolean(editingResourceKey.value)
    const payload = buildResourcePayload()
    const savedResource = wasEditing ? await api.updatePermissionResource(editingResourceKey.value, payload) : await api.createPermissionResource(payload)
    await reloadCatalogAndResources()
    showCreateResourceForm.value = false
    resetResourceForm()
    message.value = `${wasEditing ? '已更新' : '已新增'}权限资源 ${savedResource.label}`
  } catch (err) {
    actionError.value = extractApiMessage(err, editingResourceKey.value ? '更新权限资源失败' : '创建权限资源失败')
  } finally {
    creatingResource.value = false
  }
}

async function deleteResource(key: PermissionKey) {
  const resource = permissionResourceByKey(key)
  if (!canManagePermissions.value || !resource || resource.built_in || !(await confirmDiscardChanges())) return
  try {
    await ElMessageBox.confirm(`确认删除权限资源“${resource.label}”？`, '删除权限资源', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
  } catch {
    return
  }

  deletingResource.value = key
  message.value = ''
  actionError.value = ''
  try {
    await api.deletePermissionResource(key)
    if (draftPermissions.value.has(key)) {
      const next = new Set(draftPermissions.value)
      next.delete(key)
      draftPermissions.value = next
    }
    await Promise.all([loadPermissionData(), refreshRoles(), refreshPermissionResources(), loadCurrentUser()])
    message.value = `已删除权限资源 ${resource.label}`
  } catch (err) {
    actionError.value = extractApiMessage(err, '删除权限资源失败')
  } finally {
    deletingResource.value = ''
  }
}

async function savePermissions() {
  if (!selectedRoleDefinition.value || !canSavePermissions.value) return

  saving.value = true
  message.value = ''
  actionError.value = ''
  try {
    const updatedRole = await api.updateRolePermissions(selectedRole.value, Array.from(draftPermissions.value))
    roleDefinitions.value = roleDefinitions.value.map((role) => (role.key === updatedRole.key ? updatedRole : role))
    resetDraft(updatedRole)
    await refreshRoles()
    await loadCurrentUser()
    message.value = `已保存 ${updatedRole.label} 的权限配置`
  } catch (err) {
    actionError.value = extractApiMessage(err, '保存失败，请检查权限组合是否有效')
  } finally {
    saving.value = false
  }
}

onMounted(loadPermissionData)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p class="eyebrow">Access Control</p>
        <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">权限管理</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">按角色配置页面、接口和按钮权限。可手动新增角色、菜单路由、按钮和 API 权限点。</p>
      </div>
      <div v-if="canManagePermissions" class="flex flex-wrap items-center justify-end gap-3">
        <el-button native-type="button" @click="openCreateResourceForm">
          <Plus class="h-4 w-4" />新增权限资源
        </el-button>
        <el-button native-type="button" @click="openCreateRoleForm">
          <Plus class="h-4 w-4" />新增角色
        </el-button>
        <el-button
          type="primary"
          native-type="button"
          :loading="saving"
          :disabled="!canSavePermissions"
          @click="savePermissions"
        >
          <Save class="h-4 w-4" />{{ saving ? '保存中...' : isDirty ? '保存配置' : '无更改' }}
        </el-button>
      </div>
    </div>

    <el-card v-if="loading" shadow="never" class="rounded-2xl text-sm text-slate-500">正在加载权限配置...</el-card>
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <template v-else>
      <el-alert v-if="message" :title="message" type="success" show-icon :closable="false" />
      <el-alert v-if="actionError" :title="actionError" type="error" show-icon :closable="false" />

      <el-dialog v-if="canManagePermissions" v-model="showCreateRoleForm" width="720px" :before-close="closeCreateRoleForm">
        <template #header>
          <div>
            <p class="eyebrow">New Role</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">新增角色</h2>
            <p class="mt-1 text-sm text-slate-500">新角色默认授予“查看控制台”，创建后可继续在右侧勾选权限并保存。</p>
          </div>
        </template>
        <div class="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">角色编码</span>
            <el-input v-model.trim="newRoleKey" class="mt-2 w-full" placeholder="regional_manager" />
            <span class="mt-1 block text-xs text-slate-400">小写字母开头，仅小写字母/数字/下划线，3-32 位</span>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">角色名称</span>
            <el-input v-model.trim="newRoleLabel" class="mt-2 w-full" placeholder="区域经理" />
            <span class="mt-1 block text-xs text-slate-400">用于角色列表、演示角色下拉和权限配置展示</span>
          </label>
        </div>
        <template #footer>
          <div class="flex justify-end gap-3">
            <el-button native-type="button" @click="closeCreateRoleForm">取消</el-button>
            <el-button type="primary" native-type="button" :loading="creating" :disabled="!canCreateRole || creating" @click="createRole">
              <Plus class="h-4 w-4" />{{ creating ? '创建中...' : '创建角色' }}
            </el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog v-if="canManagePermissions" v-model="showCreateResourceForm" width="900px" :before-close="closeResourceForm">
        <template #header>
          <div>
            <p class="eyebrow">{{ editingResourceKey ? 'Edit Permission Resource' : 'New Permission Resource' }}</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">{{ editingResourceKey ? '编辑权限资源' : '新增权限资源' }}</h2>
            <p class="mt-1 text-sm text-slate-500">可新增菜单路由、按钮或 API 权限点。内置权限资源不可编辑或删除。</p>
          </div>
        </template>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">资源类型</span>
            <el-select v-model="resourceType" class="mt-2 w-full">
              <el-option label="菜单/路由" value="menu" />
              <el-option label="按钮" value="button" />
              <el-option label="API/数据" value="api" />
            </el-select>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限编码</span>
            <el-input v-model.trim="resourceKey" class="mt-2 w-full" placeholder="reports:view" :disabled="Boolean(editingResourceKey)" />
            <span class="mt-1 block text-xs text-slate-400">格式：resource:action，例如 reports:view</span>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限名称</span>
            <el-input v-model.trim="resourceLabel" class="mt-2 w-full" placeholder="查看报表" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">分组编码</span>
            <el-input v-model.trim="resourceGroup" class="mt-2 w-full" placeholder="reports" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">分组名称</span>
            <el-input v-model.trim="resourceGroupLabel" class="mt-2 w-full" placeholder="报表中心" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限描述</span>
            <el-input v-model.trim="resourceDescription" class="mt-2 w-full" placeholder="查看经营报表和统计数据" />
          </label>
        </div>

        <el-card v-if="resourceType === 'menu'" shadow="never" class="mt-4 rounded-2xl bg-slate-50">
          <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <label class="block">
              <span class="text-sm font-semibold text-slate-700">菜单名称</span>
              <el-input v-model.trim="resourceMenuLabel" class="mt-2 w-full" placeholder="报表中心" />
            </label>
            <label class="block">
              <span class="text-sm font-semibold text-slate-700">菜单副标题</span>
              <el-input v-model.trim="resourceMenuHint" class="mt-2 w-full" placeholder="经营分析" />
            </label>
            <label class="block">
              <span class="text-sm font-semibold text-slate-700">路由地址</span>
              <el-input v-model.trim="resourceRoute" class="mt-2 w-full" placeholder="/custom/reports" />
              <span class="mt-1 block text-xs text-slate-400">必须使用 /custom/&lt;slug&gt; 格式</span>
            </label>
          </div>
        </el-card>

        <template #footer>
          <div class="flex justify-end gap-3">
            <el-button native-type="button" @click="closeResourceForm">取消</el-button>
            <el-button type="primary" native-type="button" :loading="creatingResource" :disabled="!canSubmitResource || creatingResource" @click="submitResource">
              <Plus class="h-4 w-4" />{{ creatingResource ? '保存中...' : editingResourceKey ? '保存权限资源' : '创建权限资源' }}
            </el-button>
          </div>
        </template>
      </el-dialog>

      <div class="grid grid-cols-1 gap-6 xl:grid-cols-[320px_1fr]">
        <el-card shadow="never" class="rounded-2xl overflow-hidden">
          <div class="border-b border-slate-200 pb-5">
            <p class="eyebrow">Roles</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">角色列表</h2>
            <el-input v-model="roleSearch" class="mt-4" clearable placeholder="搜索角色" />
          </div>
          <div class="mt-4 space-y-2">
            <button
              v-for="role in filteredRoles"
              :key="role.key"
              type="button"
              :class="[
                'flex w-full items-center justify-between gap-3 rounded-xl px-4 py-3 text-left transition',
                selectedRole === role.key ? 'bg-brand-900 text-white' : 'bg-slate-50 text-slate-900 hover:bg-slate-100',
              ]"
              @click="selectRole(role)"
            >
              <span>
                <span class="block font-semibold">{{ role.label }}</span>
                <span class="mt-1 block text-xs opacity-80">{{ role.key }}</span>
              </span>
              <span class="flex items-center gap-2">
                <span v-if="role.built_in" class="rounded-full bg-white/80 px-2 py-1 text-[11px] font-bold text-slate-500">内置</span>
                <span class="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">{{ role.permissions.length }}</span>
              </span>
            </button>
            <p v-if="filteredRoles.length === 0" class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">没有匹配角色</p>
          </div>
        </el-card>

        <div class="space-y-5">
          <el-card shadow="never" class="rounded-2xl">
            <div class="flex items-start justify-between gap-4">
              <div class="flex items-start gap-3">
                <div class="grid h-11 w-11 place-items-center rounded-xl bg-brand-900 text-white">
                  <ShieldCheck class="h-5 w-5" />
                </div>
                <div>
                  <div v-if="editingRole" class="flex flex-wrap items-center gap-2">
                    <el-input v-model.trim="editingRoleLabel" class="w-full sm:w-64" placeholder="角色名称" />
                    <el-button size="small" type="primary" :loading="updatingRole" :disabled="!editingRoleLabel.trim()" @click="updateSelectedRole">保存名称</el-button>
                    <el-button size="small" @click="cancelEditRole">取消</el-button>
                  </div>
                  <template v-else>
                    <h2 class="section-title">{{ selectedRoleDefinition?.label }} 权限配置</h2>
                    <p class="mt-1 text-sm text-slate-500">
                      已选择 {{ selectedCount }} / {{ allPermissionCount }} 项权限
                      <span v-if="selectedRoleDefinition?.built_in"> · 内置角色仅可调整权限</span>
                      <span v-else-if="isDirty" class="text-amber-600"> · 有未保存更改</span>
                    </p>
                  </template>
                </div>
              </div>
              <div class="flex flex-wrap items-center justify-end gap-2">
                <el-button v-if="selectedRoleIsEditable && !editingRole" size="small" @click="startEditRole">编辑角色</el-button>
                <el-button v-if="selectedRoleIsEditable" size="small" type="danger" plain :loading="deletingRole" @click="deleteSelectedRole">删除角色</el-button>
                <StatusChip :status="canManagePermissions ? 'active' : 'terminated'" />
                <span class="text-xs font-medium text-slate-500">当前角色：{{ currentRole }}</span>
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="rounded-2xl">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p class="eyebrow">Permissions</p>
                <h2 class="mt-2 text-xl font-semibold text-slate-950">权限资源</h2>
              </div>
              <el-input v-model="permissionSearch" class="w-full md:w-72" clearable placeholder="搜索权限编码、名称或描述" />
            </div>
          </el-card>

          <div class="grid grid-cols-1 gap-5 2xl:grid-cols-2">
            <el-card v-for="group in filteredCatalog" :key="group.key" shadow="never" class="rounded-2xl">
              <div class="mb-4 flex items-center justify-between">
                <h3 class="font-semibold text-slate-950">{{ group.label }}</h3>
                <span class="text-xs font-semibold text-slate-400">{{ group.permissions.length }} 项</span>
              </div>
              <div class="space-y-3">
                <div
                  v-for="permission in group.permissions"
                  :key="permission.key"
                  :class="[
                    'rounded-xl border p-3 transition',
                    isChecked(permission.key) ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50/60 hover:bg-slate-50',
                    !selectedRolePermissionsAreEditable ? 'cursor-not-allowed opacity-70' : '',
                  ]"
                >
                  <div class="flex items-start gap-3">
                    <el-checkbox
                      class="mt-0.5 shrink-0"
                      :model-value="isChecked(permission.key)"
                      :disabled="!selectedRolePermissionsAreEditable"
                      @change="togglePermission(permission.key)"
                    />
                    <span class="min-w-0 flex-1">
                      <span class="block text-sm font-semibold text-slate-900">{{ permission.label }}</span>
                      <span class="mt-1 block break-all text-xs leading-5 text-slate-500">{{ permission.key }} · {{ permission.description }}</span>
                      <span class="mt-2 flex flex-wrap items-center gap-2">
                        <span v-if="permission.type" class="inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">{{ permission.type }}</span>
                        <span v-if="permission.built_in" class="inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">内置</span>
                      </span>
                    </span>
                    <div v-if="canManagePermissions && !permission.built_in" class="flex shrink-0 flex-col gap-2">
                      <el-button size="small" text @click="openEditResourceForm(permission.key)">编辑</el-button>
                      <el-button size="small" text type="danger" :loading="deletingResource === permission.key" @click="deleteResource(permission.key)">删除</el-button>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
            <el-card v-if="filteredCatalog.length === 0" shadow="never" class="rounded-2xl text-sm text-slate-500">没有匹配权限</el-card>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
