<script setup lang="ts">
import { computed, ref } from 'vue'
import { Building2, Lock, UserRound } from '@lucide/vue'
import { ApiError } from '@/services/api'
import { demoAccountsEnabled, usePermissions } from '@/composables/usePermissions'
import type { RoleKey } from '@/types/auth'

const emit = defineEmits<{
  success: []
}>()

const { login, loadingPermissions, setRole } = usePermissions()
const username = ref('')
const password = ref('')
const error = ref('')

const canSubmit = computed(() => username.value.trim().length > 0 && password.value.length > 0 && !loadingPermissions.value)
const demoAccounts: Array<{ label: string; role: RoleKey }> = [
  { label: '系统管理员', role: 'super_admin' },
  { label: '运营经理', role: 'manager' },
  { label: '只读访客', role: 'viewer' },
]

async function loginDemo(role: RoleKey) {
  error.value = ''
  try {
    await setRole(role)
    emit('success')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '演示登录失败'
  }
}

async function submitLogin() {
  if (!canSubmit.value) return
  error.value = ''
  try {
    await login(username.value.trim(), password.value)
    emit('success')
  } catch (err) {
    if (err instanceof ApiError && typeof err.detail === 'object' && err.detail && 'detail' in err.detail) {
      const detail = err.detail.detail
      if (typeof detail === 'object' && detail && 'message' in detail && typeof detail.message === 'string') {
        error.value = detail.message
        return
      }
    }
    error.value = err instanceof Error ? err.message : '登录失败'
  }
}
</script>

<template>
  <main class="min-h-screen bg-surface px-4 py-6 text-slate-900 sm:px-6 sm:py-10">
    <div class="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center justify-center gap-10">
      <section class="hidden flex-1 lg:block">
        <div class="rounded-[2rem] bg-brand-900 p-10 text-white shadow-2xl shadow-brand-900/20">
          <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
            <Building2 class="h-8 w-8 text-emerald-300" />
          </div>
          <p class="mt-10 text-sm font-semibold uppercase tracking-[0.3em] text-emerald-200">Propertied</p>
          <h1 class="mt-4 max-w-xl text-4xl font-bold tracking-[-0.04em]">公寓运营系统权限中心</h1>
          <p class="mt-4 max-w-lg text-sm leading-7 text-slate-300">使用持久化角色权限和登录态访问业务数据。不同角色会看到不同菜单、按钮和接口权限。</p>
        </div>
      </section>

      <section class="w-full max-w-md rounded-[2rem] bg-white p-6 sm:p-8 shadow-xl shadow-slate-200/80 ring-1 ring-slate-200">
        <div>
          <p class="eyebrow">Sign in</p>
          <h2 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">登录系统</h2>
          <p class="mt-2 text-sm text-slate-500">请输入账号密码。</p>
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="submitLogin">
          <label class="block">
            <span class="text-sm font-semibold text-slate-700">用户名</span>
            <span class="mt-2 flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 focus-within:border-brand-900 focus-within:ring-4 focus-within:ring-brand-900/10">
              <UserRound class="h-4 w-4 text-slate-400" />
              <input v-model="username" data-testid="login-username" class="w-full bg-transparent text-sm outline-none" autocomplete="username" />
            </span>
          </label>

          <label class="block">
            <span class="text-sm font-semibold text-slate-700">密码</span>
            <span class="mt-2 flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 focus-within:border-brand-900 focus-within:ring-4 focus-within:ring-brand-900/10">
              <Lock class="h-4 w-4 text-slate-400" />
              <input v-model="password" data-testid="login-password" class="w-full bg-transparent text-sm outline-none" type="password" autocomplete="current-password" />
            </span>
          </label>

          <p v-if="error" class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">{{ error }}</p>

          <button class="primary-button h-11 w-full justify-center" type="submit" :disabled="!canSubmit">
            {{ loadingPermissions ? '登录中...' : '登录' }}
          </button>
        </form>

        <div v-if="demoAccountsEnabled" class="mt-6 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <p class="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">Demo Accounts</p>
          <div class="mt-3 grid gap-2">
            <button v-for="account in demoAccounts" :key="account.role" class="flex items-center justify-between rounded-xl bg-white px-3 py-2 text-left text-sm ring-1 ring-slate-200 transition hover:bg-slate-100" type="button" @click="loginDemo(account.role)">
              <span class="font-semibold text-slate-800">{{ account.label }}</span>
              <span class="font-mono text-xs text-slate-500">演示登录</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>
