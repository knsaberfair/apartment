METRICS = [
    {"label": "总房源", "value": "248", "change": "+12 本月新增", "tone": "primary"},
    {"label": "出租率", "value": "92.8%", "change": "+3.4% 较上月", "tone": "success"},
    {"label": "本月收入", "value": "¥482,600", "change": "+8.2% 较上月", "tone": "success"},
    {"label": "待办事项", "value": "36", "change": "12 项高优先级", "tone": "warning"},
]

PROPERTIES = [
    {"id": "P-1201", "building": "A 栋", "room": "1201", "layout": "两室一厅", "area": 78.5, "rent": 6800, "status": "occupied", "tenant": "林思远", "lease_end": "2027-03-18", "tags": ["南向", "近地铁"]},
    {"id": "P-1202", "building": "A 栋", "room": "1202", "layout": "一室一厅", "area": 52.0, "rent": 5200, "status": "vacant", "tenant": None, "lease_end": None, "tags": ["精装", "可看房"]},
    {"id": "P-1608", "building": "A 栋", "room": "1608", "layout": "三室两厅", "area": 108.0, "rent": 9600, "status": "reserved", "tenant": "赵安琪", "lease_end": "2027-07-01", "tags": ["江景", "新签约"]},
    {"id": "P-0806", "building": "B 栋", "room": "0806", "layout": "两室一厅", "area": 74.0, "rent": 6500, "status": "maintenance", "tenant": None, "lease_end": None, "tags": ["维修中"]},
    {"id": "P-2103", "building": "C 栋", "room": "2103", "layout": "一室一厅", "area": 48.0, "rent": 4900, "status": "occupied", "tenant": "周沐", "lease_end": "2026-08-22", "tags": ["即将到期"]},
    {"id": "P-1905", "building": "C 栋", "room": "1905", "layout": "复式", "area": 132.0, "rent": 12800, "status": "occupied", "tenant": "陈予白", "lease_end": "2027-01-10", "tags": ["高端房源"]},
]

TENANTS = [
    {"id": "T-10001", "name": "林思远", "phone": "138****0921", "room": "A-1201", "contract_id": "C-2026-0318", "payment_status": "paid", "move_in_date": "2026-03-18", "lease_end": "2027-03-18", "balance": 0},
    {"id": "T-10002", "name": "赵安琪", "phone": "136****8273", "room": "A-1608", "contract_id": "C-2026-0701", "payment_status": "pending", "move_in_date": "2026-07-01", "lease_end": "2027-07-01", "balance": 9600},
    {"id": "T-10003", "name": "周沐", "phone": "159****1130", "room": "C-2103", "contract_id": "C-2025-0822", "payment_status": "overdue", "move_in_date": "2025-08-22", "lease_end": "2026-08-22", "balance": 4900},
    {"id": "T-10004", "name": "陈予白", "phone": "131****6208", "room": "C-1905", "contract_id": "C-2026-0110", "payment_status": "paid", "move_in_date": "2026-01-10", "lease_end": "2027-01-10", "balance": 0},
    {"id": "T-10005", "name": "沈嘉禾", "phone": "188****7331", "room": "B-1402", "contract_id": "C-2025-1216", "payment_status": "paid", "move_in_date": "2025-12-16", "lease_end": "2026-12-16", "balance": 0},
]

CONTRACTS = [
    {"id": "C-2026-0318", "tenant": "林思远", "room": "A-1201", "start_date": "2026-03-18", "end_date": "2027-03-18", "monthly_rent": 6800, "deposit": 13600, "status": "active", "days_left": 247},
    {"id": "C-2026-0701", "tenant": "赵安琪", "room": "A-1608", "start_date": "2026-07-01", "end_date": "2027-07-01", "monthly_rent": 9600, "deposit": 19200, "status": "pending", "days_left": 352},
    {"id": "C-2025-0822", "tenant": "周沐", "room": "C-2103", "start_date": "2025-08-22", "end_date": "2026-08-22", "monthly_rent": 4900, "deposit": 9800, "status": "expiring", "days_left": 39},
    {"id": "C-2026-0110", "tenant": "陈予白", "room": "C-1905", "start_date": "2026-01-10", "end_date": "2027-01-10", "monthly_rent": 12800, "deposit": 25600, "status": "active", "days_left": 180},
    {"id": "C-2025-0612", "tenant": "王知夏", "room": "B-1109", "start_date": "2025-06-12", "end_date": "2026-06-12", "monthly_rent": 6100, "deposit": 12200, "status": "terminated", "days_left": 0},
]

MAINTENANCE_ORDERS = [
    {"id": "M-240714-01", "title": "空调制冷异常", "room": "B-0806", "tenant": "待出租", "category": "家电", "priority": "urgent", "status": "in_progress", "assignee": "维修组-刘工", "created_at": "2026-07-14", "due_at": "今日 18:00"},
    {"id": "M-240713-08", "title": "卫生间地漏反味", "room": "C-2103", "tenant": "周沐", "category": "管道", "priority": "high", "status": "open", "assignee": "客服-苏晴", "created_at": "2026-07-13", "due_at": "明日 12:00"},
    {"id": "M-240712-03", "title": "门锁电池电量低", "room": "A-1201", "tenant": "林思远", "category": "智能门锁", "priority": "medium", "status": "waiting", "assignee": "工程-张扬", "created_at": "2026-07-12", "due_at": "07-16"},
    {"id": "M-240711-11", "title": "墙面补漆", "room": "A-1608", "tenant": "赵安琪", "category": "装修", "priority": "low", "status": "resolved", "assignee": "维修组-刘工", "created_at": "2026-07-11", "due_at": "已完成"},
]

TRANSACTIONS = [
    {"id": "F-20260714-001", "date": "2026-07-14", "type": "租金收入", "room": "A-1201", "tenant": "林思远", "amount": 6800, "method": "银行转账", "status": "reconciled", "note": "7 月租金"},
    {"id": "F-20260714-002", "date": "2026-07-14", "type": "押金收入", "room": "A-1608", "tenant": "赵安琪", "amount": 19200, "method": "支付宝", "status": "pending", "note": "新签合同押金"},
    {"id": "F-20260713-006", "date": "2026-07-13", "type": "维修支出", "room": "B-0806", "tenant": "-", "amount": -860, "method": "企业微信", "status": "paid", "note": "空调检修预付款"},
    {"id": "F-20260712-003", "date": "2026-07-12", "type": "租金收入", "room": "C-2103", "tenant": "周沐", "amount": 4900, "method": "银行转账", "status": "overdue", "note": "待确认到账"},
    {"id": "F-20260710-009", "date": "2026-07-10", "type": "租金收入", "room": "C-1905", "tenant": "陈予白", "amount": 12800, "method": "银行转账", "status": "reconciled", "note": "7 月租金"},
]

RECONCILIATION = [
    {"id": "R-001", "date": "2026-07-14", "bank_flow_id": "BK202607140091", "system_flow_id": "F-20260714-001", "payer": "林思远", "amount": 6800, "channel": "招商银行", "status": "matched", "difference": 0},
    {"id": "R-002", "date": "2026-07-14", "bank_flow_id": "AL202607140332", "system_flow_id": "F-20260714-002", "payer": "赵安琪", "amount": 19200, "channel": "支付宝", "status": "pending", "difference": 0},
    {"id": "R-003", "date": "2026-07-13", "bank_flow_id": "WX202607130882", "system_flow_id": "F-20260713-006", "payer": "物业维修供应商", "amount": -860, "channel": "企业微信", "status": "matched", "difference": 0},
    {"id": "R-004", "date": "2026-07-12", "bank_flow_id": "BK202607120014", "system_flow_id": "F-20260712-003", "payer": "周沐", "amount": 4700, "channel": "建设银行", "status": "exception", "difference": -200},
]

DASHBOARD_SUMMARY = {
    "metrics": METRICS,
    "occupancy_rate": 93,
    "monthly_income": 482600,
    "pending_tasks": 36,
    "expiring_contracts": 12,
    "recent_contracts": CONTRACTS[:4],
    "urgent_work_orders": MAINTENANCE_ORDERS[:3],
    "income_trend": [
        {"month": "2月", "income": 392000},
        {"month": "3月", "income": 418000},
        {"month": "4月", "income": 436000},
        {"month": "5月", "income": 451000},
        {"month": "6月", "income": 462000},
        {"month": "7月", "income": 482600},
    ],
}
