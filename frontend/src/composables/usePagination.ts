import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

type MaybeRef<T> = Ref<T> | ComputedRef<T>

interface PaginationOptions {
  pageSize?: number
  pageSizes?: number[]
}

export function usePagination<T>(items: MaybeRef<T[]>, options: PaginationOptions = {}) {
  const currentPage = ref(1)
  const pageSize = ref(options.pageSize ?? 10)
  const pageSizes = options.pageSizes ?? [10, 20, 50, 100]

  const total = computed(() => items.value.length)
  const maxPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const paginatedItems = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return items.value.slice(start, start + pageSize.value)
  })

  function normalizeCurrentPage() {
    if (currentPage.value > maxPage.value) {
      currentPage.value = maxPage.value
    }
    if (currentPage.value < 1) {
      currentPage.value = 1
    }
  }

  function resetPage() {
    currentPage.value = 1
  }

  function handleSizeChange(size: number) {
    pageSize.value = size
    resetPage()
  }

  function handleCurrentChange(page: number) {
    currentPage.value = page
    normalizeCurrentPage()
  }

  watch(
    () => items.value,
    () => {
      resetPage()
      normalizeCurrentPage()
    },
  )

  watch([pageSize, total], normalizeCurrentPage)

  return {
    currentPage,
    pageSize,
    pageSizes,
    paginatedItems,
    resetPage,
    handleSizeChange,
    handleCurrentChange,
  }
}
