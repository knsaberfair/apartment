<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Save, ShieldCheck } from '@lucide/vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api } from '@/services/api'
import type { PermissionGroup, PermissionKey, PermissionResourceType, RoleDefinition, RoleKey } from '@/types/auth'

const catalog = ref<PermissionGroup[]>([])
const roleDefinitions = ref<RoleDefinition[]>([])
const selectedRole = ref<RoleKey>('manager')
const draftPermissions = ref<Set<PermissionKey>>(new Set())
const loading = ref(true)
const saving = ref(false)
const creating = ref(false)
const creatingResource = ref(false)
const showCreateRoleForm = ref(false)
const showCreateResourceForm = ref(false)
const newRoleKey = ref('')
const newRoleLabel = ref('')
const resourceType = ref<PermissionResourceType>('menu')
const resourceKey = ref('')
const resourceLabel = ref('')
const resourceDescription = ref('')
const resourceGroup = ref('')
const resourceGroupLabel = ref('')
const resourceRoute = ref('')
const resourceMenuLabel = ref('')
const resourceMenuHint = ref('')
const message = ref('')
const loadError = ref('')
const actionError = ref('')

const { currentRole, hasPermission, loadCurrentUser, refreshPermissionResources, refreshRoles } = usePermissions()
const canManagePermissions = computed(() => hasPermission(pageActionPermissions.permissionManage))
const selectedRoleDefinition = computed(() => roleDefinitions.value.find((role) => role.key === selectedRole.value) ?? null)
const allPermissionCount = computed(() => catalog.value.reduce((count, group) => count + group.permissions.length, 0))
const selectedCount = computed(() => draftPermissions.value.size)
const roleKeyPattern = /^[a-z][a-z0-9_]{2,31}$/
const permissionKeyPattern = /^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$/
const customRoutePattern = /^\/custom\/[a-z][a-z0-9_-]{1,63}$/
const canCreateRole = computed(() => canManagePermissions.value && roleKeyPattern.test(newRoleKey.value) && newRoleLabel.value.trim().length > 0)
const canCreateResource = computed(() => {
  const baseValid =
    canManagePermissions.value &&
    permissionKeyPattern.test(resourceKey.value) &&
    resourceLabel.value.trim().length > 0 &&
    resourceDescription.value.trim().length > 0 &&
    resourceGroup.value.trim().length > 0 &&
    resourceGroupLabel.value.trim().length > 0

  if (!baseValid) return false
  if (resourceType.value !== 'menu') return true
  return customRoutePattern.test(resourceRoute.value) && resourceMenuLabel.value.trim().length > 0
})

const defaultNewRolePermissions: PermissionKey[] = ['dashboard:view']

function resetDraft(role: RoleDefinition | null) {
  draftPermissions.value = new Set(role?.permissions ?? [])
}

function selectRole(role: RoleDefinition) {
  selectedRole.value = role.key
  resetDraft(role)
  message.value = ''
  actionError.value = ''
}

function openCreateRoleForm() {
  showCreateRoleForm.value = true
  showCreateResourceForm.value = false
  newRoleKey.value = ''
  newRoleLabel.value = ''
  message.value = ''
  actionError.value = ''
}

function openCreateResourceForm() {
  showCreateResourceForm.value = true
  showCreateRoleForm.value = false
  resourceType.value = 'menu'
  resourceKey.value = ''
  resourceLabel.value = ''
  resourceDescription.value = ''
  resourceGroup.value = ''
  resourceGroupLabel.value = ''
  resourceRoute.value = ''
  resourceMenuLabel.value = ''
  resourceMenuHint.value = ''
  message.value = ''
  actionError.value = ''
}

function isCriticalSuperAdminPermission(permission: PermissionKey) {
  return selectedRole.value === 'super_admin' && (permission === 'permissions:view' || permission === 'permissions:manage')
}

function isChecked(permission: PermissionKey) {
  return draftPermissions.value.has(permission)
}

function togglePermission(permission: PermissionKey) {
  if (!canManagePermissions.value || isCriticalSuperAdminPermission(permission)) return

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
    const [catalogResponse, rolesResponse] = await Promise.all([api.permissionCatalog(), api.permissionRoles()])
    catalog.value = catalogResponse
    roleDefinitions.value = rolesResponse
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
    selectRole(createdRole)
    showCreateRoleForm.value = false
    message.value = `已创建角色 ${createdRole.label}，可继续勾选权限并保存`
  } catch (err) {
    actionError.value = extractApiMessage(err, '创建角色失败')
  } finally {
    creating.value = false
  }
}

async function createResource() {
  if (!canCreateResource.value) return

  creatingResource.value = true
  message.value = ''
  actionError.value = ''
  try {
    const createdResource = await api.createPermissionResource({
      key: resourceKey.value.trim(),
      label: resourceLabel.value.trim(),
      description: resourceDescription.value.trim(),
      group: resourceGroup.value.trim(),
      group_label: resourceGroupLabel.value.trim(),
      type: resourceType.value,
      route: resourceType.value === 'menu' ? resourceRoute.value.trim() : null,
      menu_label: resourceType.value === 'menu' ? resourceMenuLabel.value.trim() : null,
      menu_hint: resourceType.value === 'menu' ? resourceMenuHint.value.trim() : null,
    })
    catalog.value = await api.permissionCatalog()
    await refreshPermissionResources()
    showCreateResourceForm.value = false
    message.value = `已新增${createdResource.type === 'menu' ? '菜单' : createdResource.type === 'button' ? '按钮' : '接口'}权限 ${createdResource.label}，可在角色权限中勾选授权`
  } catch (err) {
    actionError.value = extractApiMessage(err, '创建权限资源失败')
  } finally {
    creatingResource.value = false
  }
}

async function savePermissions() {
  if (!selectedRoleDefinition.value || !canManagePermissions.value) return

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
    <div class="flex items-end justify-between gap-4">
      <div>
        <p class="eyebrow">Access Control</p>
        <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">权限管理</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">按角色配置页面、接口和按钮权限。可手动新增角色、菜单路由、按钮和 API 权限点。</p>
      </div>
      <div v-if="canManagePermissions" class="flex items-center gap-3">
        <button class="secondary-button" type="button" @click="openCreateResourceForm">
          <Plus class="h-4 w-4" />新增权限资源
        </button>
        <button class="secondary-button" type="button" @click="openCreateRoleForm">
          <Plus class="h-4 w-4" />新增角色
        </button>
        <button
          class="primary-button"
          type="button"
          :disabled="saving || loading"
          @click="savePermissions"
        >
          <Save class="h-4 w-4" />{{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="panel p-8 text-sm text-slate-500">正在加载权限配置...</div>
    <div v-else-if="loadError" class="panel border-rose-200 bg-rose-50 p-5 text-sm font-medium text-rose-700">{{ loadError }}</div>

    <template v-else>
      <div v-if="message" class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{{ message }}</div>
      <div v-if="actionError" class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">{{ actionError }}</div>

      <div v-if="showCreateRoleForm && canManagePermissions" class="panel p-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="eyebrow">New Role</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">新增角色</h2>
            <p class="mt-1 text-sm text-slate-500">新角色默认授予“查看控制台”，创建后可继续在右侧勾选更多权限并保存。</p>
          </div>
          <button class="text-sm font-semibold text-slate-500 hover:text-slate-900" type="button" @click="showCreateRoleForm = false">取消</button>
        </div>
        <div class="mt-5 grid grid-cols-[1fr_1fr_auto] items-start gap-4">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">角色编码</span>
            <input v-model.trim="newRoleKey" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="regional_manager" />
            <span class="mt-1 block text-xs text-slate-400">小写字母开头，仅小写字母/数字/下划线，3-32 位</span>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">角色名称</span>
            <input v-model.trim="newRoleLabel" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="区域经理" />
            <span class="mt-1 block text-xs text-slate-400">用于角色列表、演示角色下拉和权限配置展示</span>
          </label>
          <button class="primary-button mt-7" type="button" :disabled="!canCreateRole || creating" @click="createRole">
            <Plus class="h-4 w-4" />{{ creating ? '创建中...' : '创建角色' }}
          </button>
        </div>
      </div>

      <div v-if="showCreateResourceForm && canManagePermissions" class="panel p-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="eyebrow">New Permission Resource</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">新增权限资源</h2>
            <p class="mt-1 text-sm text-slate-500">可新增菜单路由、按钮或 API 权限点。菜单类型授权后会显示在侧边栏并进入通用占位页。</p>
          </div>
          <button class="text-sm font-semibold text-slate-500 hover:text-slate-900" type="button" @click="showCreateResourceForm = false">取消</button>
        </div>

        <div class="mt-5 grid grid-cols-3 gap-4">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">资源类型</span>
            <select v-model="resourceType" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10">
              <option value="menu">菜单/路由</option>
              <option value="button">按钮</option>
              <option value="api">API/数据</option>
            </select>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限编码</span>
            <input v-model.trim="resourceKey" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="reports:view" />
            <span class="mt-1 block text-xs text-slate-400">格式：resource:action，例如 reports:view</span>
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限名称</span>
            <input v-model.trim="resourceLabel" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="查看报表" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">分组编码</span>
            <input v-model.trim="resourceGroup" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="reports" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">分组名称</span>
            <input v-model.trim="resourceGroupLabel" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="报表中心" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">权限描述</span>
            <input v-model.trim="resourceDescription" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="查看经营报表和统计数据" />
          </label>
        </div>

        <div v-if="resourceType === 'menu'" class="mt-4 grid grid-cols-3 gap-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">菜单名称</span>
            <input v-model.trim="resourceMenuLabel" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="报表中心" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">菜单副标题</span>
            <input v-model.trim="resourceMenuHint" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="经营分析" />
          </label>
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">路由地址</span>
            <input v-model.trim="resourceRoute" class="mt-2 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-brand-900 focus:ring-4 focus:ring-brand-900/10" placeholder="/custom/reports" />
            <span class="mt-1 block text-xs text-slate-400">必须使用 /custom/&lt;slug&gt; 格式</span>
          </label>
        </div>

        <div class="mt-5 flex justify-end">
          <button class="primary-button" type="button" :disabled="!canCreateResource || creatingResource" @click="createResource">
            <Plus class="h-4 w-4" />{{ creatingResource ? '创建中...' : '创建权限资源' }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-[320px_1fr] gap-6">
        <aside class="panel overflow-hidden">
          <div class="border-b border-slate-200 p-5">
            <p class="eyebrow">Roles</p>
            <h2 class="mt-2 text-xl font-semibold text-slate-950">角色列表</h2>
          </div>
          <div class="divide-y divide-slate-100">
            <button
              v-for="role in roleDefinitions"
              :key="role.key"
              type="button"
              :class="[
                'flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-slate-50',
                selectedRole === role.key ? 'bg-slate-100' : 'bg-white',
              ]"
              @click="selectRole(role)"
            >
              <span>
                <span class="block font-semibold text-slate-950">{{ role.label }}</span>
                <span class="mt-1 block text-xs text-slate-500">{{ role.key }}</span>
              </span>
              <span class="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">{{ role.permissions.length }}</span>
            </button>
          </div>
        </aside>

        <div class="space-y-5">
          <div class="panel p-5">
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-3">
                <div class="grid h-11 w-11 place-items-center rounded-xl bg-brand-900 text-white">
                  <ShieldCheck class="h-5 w-5" />
                </div>
                <div>
                  <h2 class="section-title">{{ selectedRoleDefinition?.label }} 权限配置</h2>
                  <p class="mt-1 text-sm text-slate-500">已选择 {{ selectedCount }} / {{ allPermissionCount }} 项权限</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <StatusChip :status="canManagePermissions ? 'active' : 'terminated'" />
                <span class="text-xs font-medium text-slate-500">当前角色：{{ currentRole }}</span>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-5">
            <article v-for="group in catalog" :key="group.key" class="panel p-5">
              <div class="mb-4 flex items-center justify-between">
                <h3 class="font-semibold text-slate-950">{{ group.label }}</h3>
                <span class="text-xs font-semibold text-slate-400">{{ group.permissions.length }} 项</span>
              </div>
              <div class="space-y-3">
                <label
                  v-for="permission in group.permissions"
                  :key="permission.key"
                  :class="[
                    'flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition',
                    isChecked(permission.key) ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50/60 hover:bg-slate-50',
                    !canManagePermissions || isCriticalSuperAdminPermission(permission.key) ? 'cursor-not-allowed opacity-70' : '',
                  ]"
                >
                  <input
                    class="mt-1 h-4 w-4 rounded border-slate-300 text-brand-900 focus:ring-brand-900"
                    type="checkbox"
                    :checked="isChecked(permission.key)"
                    :disabled="!canManagePermissions || isCriticalSuperAdminPermission(permission.key)"
                    @change="togglePermission(permission.key)"
                  />
                  <span>
                    <span class="block text-sm font-semibold text-slate-900">{{ permission.label }}</span>
                    <span class="mt-1 block text-xs leading-5 text-slate-500">{{ permission.key }} · {{ permission.description }}</span>
                    <span v-if="permission.type" class="mt-1 inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">{{ permission.type }}</span>
                  </span>
                </label>
              </div>
            </article>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
