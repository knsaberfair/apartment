<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Save, ShieldCheck } from '@lucide/vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { pageActionPermissions } from '@/config/permissions'
import { usePermissions } from '@/composables/usePermissions'
import { ApiError, api } from '@/services/api'
import type { PermissionGroup, PermissionKey, RoleDefinition, RoleKey } from '@/types/auth'

const catalog = ref<PermissionGroup[]>([])
const roleDefinitions = ref<RoleDefinition[]>([])
const selectedRole = ref<RoleKey>('manager')
const draftPermissions = ref<Set<PermissionKey>>(new Set())
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const error = ref('')

const { currentRole, hasPermission, loadCurrentUser, refreshRoles } = usePermissions()
const canManagePermissions = computed(() => hasPermission(pageActionPermissions.permissionManage))
const selectedRoleDefinition = computed(() => roleDefinitions.value.find((role) => role.key === selectedRole.value) ?? null)
const allPermissionCount = computed(() => catalog.value.reduce((count, group) => count + group.permissions.length, 0))
const selectedCount = computed(() => draftPermissions.value.size)

function resetDraft(role: RoleDefinition | null) {
  draftPermissions.value = new Set(role?.permissions ?? [])
}

function selectRole(role: RoleDefinition) {
  selectedRole.value = role.key
  resetDraft(role)
  message.value = ''
  error.value = ''
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

async function loadPermissionData() {
  loading.value = true
  error.value = ''
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
    error.value = err instanceof Error ? err.message : '加载权限配置失败'
  } finally {
    loading.value = false
  }
}

async function savePermissions() {
  if (!selectedRoleDefinition.value || !canManagePermissions.value) return

  saving.value = true
  message.value = ''
  error.value = ''
  try {
    const updatedRole = await api.updateRolePermissions(selectedRole.value, Array.from(draftPermissions.value))
    roleDefinitions.value = roleDefinitions.value.map((role) => (role.key === updatedRole.key ? updatedRole : role))
    resetDraft(updatedRole)
    await refreshRoles()
    await loadCurrentUser()
    message.value = `已保存 ${updatedRole.label} 的权限配置`
  } catch (err) {
    if (err instanceof ApiError && typeof err.detail === 'object' && err.detail && 'detail' in err.detail) {
      error.value = '保存失败，请检查权限组合是否有效'
    } else {
      error.value = err instanceof Error ? err.message : '保存失败'
    }
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
        <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">按角色配置页面、接口和按钮权限。当前配置保存在 FastAPI 内存中，适合演示和后续接入数据库。</p>
      </div>
      <button
        v-if="canManagePermissions"
        class="primary-button"
        type="button"
        :disabled="saving || loading"
        @click="savePermissions"
      >
        <Save class="h-4 w-4" />{{ saving ? '保存中...' : '保存配置' }}
      </button>
    </div>

    <div v-if="loading" class="panel p-8 text-sm text-slate-500">正在加载权限配置...</div>
    <div v-else-if="error" class="panel border-rose-200 bg-rose-50 p-5 text-sm font-medium text-rose-700">{{ error }}</div>

    <template v-else>
      <div v-if="message" class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{{ message }}</div>

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
