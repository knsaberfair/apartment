<script setup lang="ts">
import { PanelTop } from '@lucide/vue'
import { ElCard } from 'element-plus'
import type { PermissionResource } from '@/types/auth'

const props = defineProps<{
  resource: PermissionResource | null
}>()
</script>

<template>
  <section class="space-y-6">
    <div>
      <p class="eyebrow">Custom Menu</p>
      <h1 class="mt-2 text-3xl font-bold tracking-[-0.03em] text-slate-950">{{ props.resource?.menu_label || props.resource?.label || '自定义菜单' }}</h1>
      <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{{ props.resource?.menu_hint || props.resource?.description || '这是通过权限管理动态添加的菜单资源。' }}</p>
    </div>

    <el-card shadow="never" class="rounded-2xl">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div class="grid h-12 w-12 place-items-center rounded-xl bg-brand-900 text-white">
          <PanelTop class="h-6 w-6" />
        </div>
        <div class="space-y-4">
          <div>
            <h2 class="section-title">动态菜单占位页</h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">该页面用于承载手动添加的菜单/路由权限。后续如果需要真实业务页面，可以将该路由绑定到具体 Vue 页面组件或后端驱动页面配置。</p>
          </div>
          <dl class="grid grid-cols-1 gap-x-4 gap-y-3 text-sm sm:grid-cols-[120px_1fr]">
            <dt class="font-semibold text-slate-500">权限编码</dt>
            <dd class="font-mono text-slate-900">{{ props.resource?.key || '-' }}</dd>
            <dt class="font-semibold text-slate-500">路由地址</dt>
            <dd class="font-mono text-slate-900">{{ props.resource?.route || '-' }}</dd>
            <dt class="font-semibold text-slate-500">资源分组</dt>
            <dd class="text-slate-900">{{ props.resource?.group_label || '-' }}</dd>
            <dt class="font-semibold text-slate-500">资源类型</dt>
            <dd class="text-slate-900">{{ props.resource?.type || '-' }}</dd>
          </dl>
        </div>
      </div>
    </el-card>
  </section>
</template>
