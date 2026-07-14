from typing import Any

PERMISSION_CATALOG = [
    {
        "key": "dashboard",
        "label": "管理控制台",
        "permissions": [
            {"key": "dashboard:view", "label": "查看控制台", "description": "查看运营指标、趋势和待办概览"},
            {"key": "dashboard:export", "label": "导出日报", "description": "生成或导出运营日报"},
        ],
    },
    {
        "key": "properties",
        "label": "房源管理",
        "permissions": [
            {"key": "properties:view", "label": "查看房源", "description": "查看房源列表和房间状态"},
            {"key": "properties:create", "label": "新增房源", "description": "创建新的房源档案"},
            {"key": "properties:update", "label": "编辑房源", "description": "修改房源基础信息和状态"},
            {"key": "properties:delete", "label": "删除房源", "description": "删除房源档案"},
        ],
    },
    {
        "key": "tenants",
        "label": "租客管理",
        "permissions": [
            {"key": "tenants:view", "label": "查看租客", "description": "查看租客档案和入住信息"},
            {"key": "tenants:create", "label": "新增租客", "description": "创建租客档案"},
            {"key": "tenants:update", "label": "编辑租客", "description": "修改租客资料"},
            {"key": "tenants:delete", "label": "删除租客", "description": "删除租客档案"},
        ],
    },
    {
        "key": "contracts",
        "label": "合同管理",
        "permissions": [
            {"key": "contracts:view", "label": "查看合同", "description": "查看合同列表、租期和押金信息"},
            {"key": "contracts:create", "label": "新建合同", "description": "创建租赁合同"},
            {"key": "contracts:approve", "label": "审批合同", "description": "审批或确认合同生效"},
            {"key": "contracts:terminate", "label": "终止合同", "description": "办理合同终止"},
        ],
    },
    {
        "key": "maintenance",
        "label": "工单维修",
        "permissions": [
            {"key": "maintenance:view", "label": "查看工单", "description": "查看维修工单和进度"},
            {"key": "maintenance:create", "label": "创建工单", "description": "新增租客报修或维修任务"},
            {"key": "maintenance:assign", "label": "派发工单", "description": "分配维修负责人"},
            {"key": "maintenance:resolve", "label": "完成工单", "description": "标记工单完成或验收"},
        ],
    },
    {
        "key": "finance",
        "label": "财务管理",
        "permissions": [
            {"key": "finance:view", "label": "查看财务", "description": "查看财务流水和收支概览"},
            {"key": "finance:create", "label": "新增账单", "description": "创建租金、押金或支出账单"},
            {"key": "finance:export", "label": "导出财务", "description": "导出财务数据"},
        ],
    },
    {
        "key": "reconciliation",
        "label": "流水对账",
        "permissions": [
            {"key": "reconciliation:view", "label": "查看对账", "description": "查看银行流水和系统流水匹配结果"},
            {"key": "reconciliation:import", "label": "导入流水", "description": "导入银行或第三方支付流水"},
            {"key": "reconciliation:export", "label": "导出对账", "description": "导出对账单"},
        ],
    },
    {
        "key": "system",
        "label": "系统权限",
        "permissions": [
            {"key": "permissions:view", "label": "查看权限管理", "description": "进入权限管理页面并查看角色授权"},
            {"key": "permissions:manage", "label": "配置角色权限", "description": "保存角色权限配置"},
            {"key": "system:settings", "label": "系统设置", "description": "访问系统设置入口"},
            {"key": "tasks:view", "label": "查看待办", "description": "查看今日待办入口"},
        ],
    },
]

ALL_PERMISSIONS = {
    permission["key"]
    for group in PERMISSION_CATALOG
    for permission in group["permissions"]
}

ROLE_LABELS = {
    "super_admin": "系统管理员",
    "manager": "运营经理",
    "leasing_agent": "租务专员",
    "maintenance_staff": "维修人员",
    "finance_staff": "财务人员",
    "viewer": "只读访客",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": set(ALL_PERMISSIONS),
    "manager": set(ALL_PERMISSIONS) - {"system:settings"},
    "leasing_agent": {
        "dashboard:view",
        "properties:view",
        "properties:create",
        "properties:update",
        "tenants:view",
        "tenants:create",
        "tenants:update",
        "contracts:view",
        "contracts:create",
        "tasks:view",
    },
    "maintenance_staff": {
        "dashboard:view",
        "maintenance:view",
        "maintenance:create",
        "maintenance:assign",
        "maintenance:resolve",
        "tasks:view",
    },
    "finance_staff": {
        "dashboard:view",
        "contracts:view",
        "finance:view",
        "finance:create",
        "finance:export",
        "reconciliation:view",
        "reconciliation:import",
        "reconciliation:export",
        "tasks:view",
    },
    "viewer": {
        "dashboard:view",
        "properties:view",
        "tenants:view",
        "contracts:view",
        "maintenance:view",
    },
}

DEFAULT_ROLE = "viewer"


def normalize_role(role: str | None) -> str:
    if role in ROLE_PERMISSIONS:
        return role
    return DEFAULT_ROLE


def get_permissions_for_role(role: str) -> set[str]:
    return ROLE_PERMISSIONS[normalize_role(role)]


def role_has_permission(role: str, permission: str) -> bool:
    return permission in get_permissions_for_role(role)


def get_demo_user(role: str | None) -> dict[str, Any]:
    normalized_role = normalize_role(role)
    permissions = sorted(get_permissions_for_role(normalized_role))
    return {
        "id": f"demo-{normalized_role}",
        "name": ROLE_LABELS[normalized_role],
        "role": normalized_role,
        "role_label": ROLE_LABELS[normalized_role],
        "permissions": permissions,
    }


def list_roles() -> list[dict[str, Any]]:
    return [
        {
            "key": role,
            "label": ROLE_LABELS[role],
            "permissions": sorted(permissions),
        }
        for role, permissions in ROLE_PERMISSIONS.items()
    ]


def get_permission_catalog() -> list[dict[str, Any]]:
    return PERMISSION_CATALOG


def validate_permissions(permissions: set[str]) -> None:
    unknown_permissions = permissions - ALL_PERMISSIONS
    if unknown_permissions:
        unknown = ", ".join(sorted(unknown_permissions))
        raise ValueError(f"Unknown permissions: {unknown}")
    if not any(permission.endswith(":view") for permission in permissions):
        raise ValueError("At least one view permission is required")


def update_role_permissions(role: str, permissions: set[str]) -> dict[str, Any]:
    if role not in ROLE_PERMISSIONS:
        raise KeyError(role)

    validate_permissions(permissions)

    if role == "super_admin":
        required_permissions = {"permissions:view", "permissions:manage"}
        if not required_permissions.issubset(permissions):
            raise ValueError("super_admin must keep permission management access")

    ROLE_PERMISSIONS[role] = set(permissions)
    return {
        "key": role,
        "label": ROLE_LABELS[role],
        "permissions": sorted(ROLE_PERMISSIONS[role]),
    }
