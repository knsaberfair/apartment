<script setup lang="ts">
defineProps<{
  columns: string[]
  emptyText?: string
}>()
</script>

<template>
  <div class="panel overflow-hidden">
    <table class="min-w-full divide-y divide-slate-200">
      <thead class="bg-slate-100/80">
        <tr>
          <th v-for="column in columns" :key="column" class="px-5 py-3 text-left text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 bg-white text-sm text-slate-700">
        <slot />
      </tbody>
    </table>
  </div>
</template>
