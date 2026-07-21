export const statusLabels: Record<string, string> = {
  occupied: '已出租',
  vacant: '空置',
  reserved: '已预定',
  maintenance: '维修中',
  active: '生效中',
  expiring: '即将到期',
  pending: '待处理',
  terminated: '已终止',
  paid: '已支付',
  overdue: '已逾期',
  reconciled: '已对账',
  matched: '已匹配',
  exception: '异常',
  reviewed: '已复核',
  open: '待派单',
  in_progress: '处理中',
  waiting: '待确认',
  resolved: '已完成',
  low: '低',
  medium: '中',
  high: '高',
  urgent: '紧急',
}

export function statusLabel(status: string) {
  return statusLabels[status] ?? status
}
