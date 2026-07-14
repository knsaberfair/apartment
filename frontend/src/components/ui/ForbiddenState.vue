<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  {
    title: '403 无权限访问',
    description: '当前角色没有访问该资源的权限，请切换角色或联系系统管理员。',
  },
)
</script>

<template>
  <div class="panel flex min-h-[360px] flex-col items-center justify-center p-10 text-center">
    <div class="rounded-full bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 ring-1 ring-rose-100">403</div>
    <h2 class="mt-5 text-2xl font-bold tracking-[-0.02em] text-slate-950">{{ title }}</h2>
    <p class="mt-3 max-w-md text-sm leading-6 text-slate-500">{{ description }}</p>
  </div>
</template>
