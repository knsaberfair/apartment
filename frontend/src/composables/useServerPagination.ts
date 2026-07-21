import { computed, ref } from 'vue'

interface ServerPaginationOptions {
  pageSize?: number
  pageSizes?: number[]
}

export function useServerPagination(options: ServerPaginationOptions = {}) {
  const currentPage = ref(1)
  const pageSize = ref(options.pageSize ?? 10)
  const pageSizes = options.pageSizes ?? [10, 20, 50, 100]
  const total = ref(0)
  const offset = computed(() => (currentPage.value - 1) * pageSize.value)

  function normalizeCurrentPage() {
    const maxPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage
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

  return {
    currentPage,
    pageSize,
    pageSizes,
    total,
    offset,
    resetPage,
    normalizeCurrentPage,
    handleSizeChange,
    handleCurrentChange,
  }
}
