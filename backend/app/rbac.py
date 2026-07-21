from datetime import datetime, timezone
import re
import sqlite3
from typing import Any

BUILT_IN_PERMISSION_CATALOG = [
    {
        "key": "dashboard",
        "label": "管理控制台",
        "permissions": [
            {"key": "dashboard:view", "label": "查看控制台", "description": "查看运营指标、趋势和待办概览", "type": "menu", "route": "/dashboard", "menu_label": "管理控制台", "menu_hint": "运营驾驶舱", "sort": 10},
            {"key": "dashboard:export", "label": "导出日报", "description": "生成或导出运营日报", "type": "button", "sort": 11},
        ],
    },
    {
        "key": "properties",
        "label": "房源管理",
        "permissions": [
            {"key": "properties:view", "label": "查看房源", "description": "查看房源列表和房间状态", "type": "menu", "route": "/properties", "menu_label": "房源管理", "menu_hint": "楼栋与房间", "sort": 20},
            {"key": "properties:create", "label": "新增房源", "description": "创建新的房源档案", "type": "button", "sort": 21},
            {"key": "properties:update", "label": "编辑房源", "description": "修改房源基础信息和状态", "type": "button", "sort": 22},
            {"key": "properties:delete", "label": "删除房源", "description": "删除房源档案", "type": "button", "sort": 23},
        ],
    },
    {
        "key": "tenants",
        "label": "租客管理",
        "permissions": [
            {"key": "tenants:view", "label": "查看租客", "description": "查看租客档案和入住信息", "type": "menu", "route": "/tenants", "menu_label": "租客列表", "menu_hint": "住户档案", "sort": 30},
            {"key": "tenants:create", "label": "新增租客", "description": "创建租客档案", "type": "button", "sort": 31},
            {"key": "tenants:update", "label": "编辑租客", "description": "修改租客资料", "type": "button", "sort": 32},
            {"key": "tenants:delete", "label": "删除租客", "description": "删除租客档案", "type": "button", "sort": 33},
        ],
    },
    {
        "key": "contracts",
        "label": "合同管理",
        "permissions": [
            {"key": "contracts:view", "label": "查看合同", "description": "查看合同列表、租期和押金信息", "type": "menu", "route": "/contracts", "menu_label": "合同管理", "menu_hint": "租约与签署", "sort": 40},
            {"key": "contracts:create", "label": "新建合同", "description": "创建租赁合同", "type": "button", "sort": 41},
            {"key": "contracts:approve", "label": "审批合同", "description": "审批或确认合同生效", "type": "button", "sort": 42},
            {"key": "contracts:terminate", "label": "终止合同", "description": "办理合同终止", "type": "button", "sort": 43},
        ],
    },
    {
        "key": "maintenance",
        "label": "工单维修",
        "permissions": [
            {"key": "maintenance:view", "label": "查看工单", "description": "查看维修工单和进度", "type": "menu", "route": "/maintenance", "menu_label": "工单维修", "menu_hint": "报修处理", "sort": 50},
            {"key": "maintenance:create", "label": "创建工单", "description": "新增租客报修或维修任务", "type": "button", "sort": 51},
            {"key": "maintenance:assign", "label": "派发工单", "description": "分配维修负责人", "type": "button", "sort": 52},
            {"key": "maintenance:resolve", "label": "完成工单", "description": "标记工单完成或验收", "type": "button", "sort": 53},
        ],
    },
    {
        "key": "finance",
        "label": "财务管理",
        "permissions": [
            {"key": "finance:view", "label": "查看财务", "description": "查看财务流水和收支概览", "type": "menu", "route": "/finance", "menu_label": "财务管理", "menu_hint": "账单与收支", "sort": 60},
            {"key": "finance:create", "label": "新增账单", "description": "创建租金、押金或支出账单", "type": "button", "sort": 61},
            {"key": "finance:confirm", "label": "确认收款", "description": "确认待收或逾期账单已支付", "type": "button", "sort": 62},
            {"key": "finance:export", "label": "导出财务", "description": "导出财务数据", "type": "button", "sort": 63},
        ],
    },
    {
        "key": "reconciliation",
        "label": "流水对账",
        "permissions": [
            {"key": "reconciliation:view", "label": "查看对账", "description": "查看银行流水和系统流水匹配结果", "type": "menu", "route": "/reconciliation", "menu_label": "流水对账", "menu_hint": "银行流水", "sort": 70},
            {"key": "reconciliation:import", "label": "导入流水", "description": "导入银行或第三方支付流水", "type": "button", "sort": 71},
            {"key": "reconciliation:resolve", "label": "处理对账", "description": "重试匹配或复核异常对账流水", "type": "button", "sort": 72},
            {"key": "reconciliation:export", "label": "导出对账", "description": "导出对账单", "type": "button", "sort": 73},
        ],
    },
    {
        "key": "system",
        "label": "系统权限",
        "permissions": [
            {"key": "permissions:view", "label": "查看权限管理", "description": "进入权限管理页面并查看角色授权", "type": "menu", "route": "/permissions", "menu_label": "权限管理", "menu_hint": "角色与授权", "sort": 90},
            {"key": "permissions:manage", "label": "配置角色权限", "description": "保存角色、权限和资源配置", "type": "button", "sort": 91},
            {"key": "system:settings", "label": "系统设置", "description": "访问系统设置入口", "type": "button", "sort": 92},
            {"key": "audit:view", "label": "查看操作审计", "description": "查看核心业务操作审计日志", "type": "menu", "route": "/audit-logs", "menu_label": "操作日志", "menu_hint": "操作审计", "sort": 93},
            {"key": "tasks:view", "label": "查看通知提醒", "description": "查看跨模块通知、风险和待处理事项", "type": "menu", "route": "/tasks", "menu_label": "通知提醒", "menu_hint": "风险与任务", "sort": 94},
        ],
    },
]

PERMISSION_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")
ROLE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
CUSTOM_ROUTE_PATTERN = re.compile(r"^/custom/[a-z][a-z0-9_-]{1,63}$")
RESOURCE_TYPES = {"menu", "button", "api"}


def _audit_if_requested(db: sqlite3.Connection, actor: dict[str, Any] | None, action: str, resource_type: str, resource_id: str) -> None:
    if actor is None:
        return
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, actor_name, actor_role, action, resource_type, resource_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.get("id") or "unknown",
            actor.get("name") or "unknown",
            actor.get("role") or "unknown",
            action,
            resource_type,
            resource_id,
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        ),
    )


DEFAULT_ROLE = "viewer"
ROLE_LABELS = {
    "super_admin": "系统管理员",
    "manager": "运营经理",
    "leasing_agent": "租务专员",
    "maintenance_staff": "维修人员",
    "finance_staff": "财务人员",
    "viewer": "只读访客",
}


def build_builtin_permission_resources() -> dict[str, dict[str, Any]]:
    resources: dict[str, dict[str, Any]] = {}
    for group in BUILT_IN_PERMISSION_CATALOG:
        for permission in group["permissions"]:
            key = permission["key"]
            resources[key] = {
                "key": key,
                "label": permission["label"],
                "description": permission["description"],
                "group": group["key"],
                "group_label": group["label"],
                "type": permission.get("type", "api"),
                "route": permission.get("route"),
                "menu_label": permission.get("menu_label"),
                "menu_hint": permission.get("menu_hint"),
                "sort": permission.get("sort", 1000),
                "built_in": True,
            }
    return resources


BUILT_IN_PERMISSION_RESOURCES = build_builtin_permission_resources()
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": set(BUILT_IN_PERMISSION_RESOURCES),
    "manager": set(BUILT_IN_PERMISSION_RESOURCES) - {"system:settings"},
    "leasing_agent": {"dashboard:view", "properties:view", "properties:create", "properties:update", "tenants:view", "tenants:create", "tenants:update", "contracts:view", "contracts:create", "tasks:view"},
    "maintenance_staff": {"dashboard:view", "maintenance:view", "maintenance:create", "maintenance:assign", "maintenance:resolve", "tasks:view"},
    "finance_staff": {"dashboard:view", "contracts:view", "finance:view", "finance:create", "finance:confirm", "finance:export", "reconciliation:view", "reconciliation:import", "reconciliation:resolve", "reconciliation:export", "tasks:view"},
    "viewer": {"dashboard:view", "properties:view", "tenants:view", "contracts:view", "maintenance:view"},
}


def _resource_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key": row["key"],
        "label": row["label"],
        "description": row["description"],
        "group": row["group_key"],
        "group_label": row["group_label"],
        "type": row["type"],
        "route": row["route"],
        "menu_label": row["menu_label"],
        "menu_hint": row["menu_hint"],
        "sort": row["sort"],
        "built_in": bool(row["built_in"]),
    }


def get_all_permissions(db: sqlite3.Connection) -> set[str]:
    rows = db.execute("SELECT key FROM permission_resources").fetchall()
    return {row["key"] for row in rows}


def normalize_role(db: sqlite3.Connection, role: str | None) -> str:
    if role:
        row = db.execute("SELECT key FROM roles WHERE key = ?", (role,)).fetchone()
        if row:
            return role
    return DEFAULT_ROLE


def get_permissions_for_role(db: sqlite3.Connection, role: str) -> set[str]:
    normalized_role = normalize_role(db, role)
    rows = db.execute("SELECT permission_key FROM role_permissions WHERE role_key = ?", (normalized_role,)).fetchall()
    return {row["permission_key"] for row in rows}


def role_has_permission(db: sqlite3.Connection, role: str, permission: str) -> bool:
    return permission in get_permissions_for_role(db, role)


def get_role_label(db: sqlite3.Connection, role: str) -> str:
    row = db.execute("SELECT label FROM roles WHERE key = ?", (role,)).fetchone()
    return row["label"] if row else role


def build_user_response(db: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    role = user["role_key"]
    return {
        "id": user["id"],
        "name": user["display_name"],
        "role": role,
        "role_label": get_role_label(db, role),
        "permissions": sorted(get_permissions_for_role(db, role)),
    }


def get_demo_user(db: sqlite3.Connection, role: str | None) -> dict[str, Any]:
    normalized_role = normalize_role(db, role)
    return {
        "id": f"demo-{normalized_role}",
        "name": get_role_label(db, normalized_role),
        "role": normalized_role,
        "role_label": get_role_label(db, normalized_role),
        "permissions": sorted(get_permissions_for_role(db, normalized_role)),
    }


def build_role_response(db: sqlite3.Connection, role: str) -> dict[str, Any]:
    row = db.execute("SELECT key, label, built_in FROM roles WHERE key = ?", (role,)).fetchone()
    if not row:
        raise KeyError(role)
    return {
        "key": row["key"],
        "label": row["label"],
        "permissions": sorted(get_permissions_for_role(db, role)),
        "built_in": bool(row["built_in"]),
    }


def list_roles(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute("SELECT key FROM roles ORDER BY built_in DESC, key").fetchall()
    return [build_role_response(db, row["key"]) for row in rows]


def list_permission_resources(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM permission_resources ORDER BY sort, group_key, key").fetchall()
    return [_resource_from_row(row) for row in rows]


def list_menu_resources(db: sqlite3.Connection, role: str | None = None) -> list[dict[str, Any]]:
    resources = [resource for resource in list_permission_resources(db) if resource["type"] == "menu"]
    if role is None:
        return resources
    permissions = get_permissions_for_role(db, role)
    return [resource for resource in resources if resource["key"] in permissions]


def get_permission_catalog(db: sqlite3.Connection) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for resource in list_permission_resources(db):
        group_key = resource["group"]
        group = groups.setdefault(group_key, {"key": group_key, "label": resource["group_label"], "permissions": []})
        group["permissions"].append(
            {
                "key": resource["key"],
                "label": resource["label"],
                "description": resource["description"],
                "type": resource["type"],
                "route": resource.get("route"),
                "menu_label": resource.get("menu_label"),
                "menu_hint": resource.get("menu_hint"),
                "built_in": resource.get("built_in", False),
            }
        )
    return list(groups.values())


def validate_permissions(db: sqlite3.Connection, permissions: set[str]) -> None:
    unknown_permissions = permissions - get_all_permissions(db)
    if unknown_permissions:
        unknown = ", ".join(sorted(unknown_permissions))
        raise ValueError(f"Unknown permissions: {unknown}")
    if not any(permission.endswith(":view") for permission in permissions):
        raise ValueError("At least one view permission is required")


def update_role_permissions(db: sqlite3.Connection, role: str, permissions: set[str], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    row = db.execute("SELECT built_in FROM roles WHERE key = ?", (role,)).fetchone()
    if not row:
        raise KeyError(role)
    validate_permissions(db, permissions)

    with db:
        db.execute("DELETE FROM role_permissions WHERE role_key = ?", (role,))
        db.executemany(
            "INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)",
            [(role, permission) for permission in sorted(permissions)],
        )
        _audit_if_requested(db, actor, "update_permissions", "role", role)
    return build_role_response(db, role)


def create_role(db: sqlite3.Connection, role: str, label: str, permissions: set[str], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_role = role.strip()
    normalized_label = label.strip()
    if not ROLE_KEY_PATTERN.fullmatch(normalized_role):
        raise ValueError("Role key must start with a lowercase letter and contain only lowercase letters, numbers, and underscores; length 3-32")
    if db.execute("SELECT 1 FROM roles WHERE key = ?", (normalized_role,)).fetchone():
        raise KeyError(normalized_role)
    if not normalized_label:
        raise ValueError("Role label is required")
    validate_permissions(db, permissions)

    with db:
        db.execute("INSERT INTO roles (key, label, built_in) VALUES (?, ?, 0)", (normalized_role, normalized_label))
        db.executemany(
            "INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)",
            [(normalized_role, permission) for permission in sorted(permissions)],
        )
        _audit_if_requested(db, actor, "create", "role", normalized_role)
    return build_role_response(db, normalized_role)


def update_role_label(db: sqlite3.Connection, role: str, label: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_label = label.strip()
    row = db.execute("SELECT built_in FROM roles WHERE key = ?", (role,)).fetchone()
    if not row:
        raise KeyError(role)
    if row["built_in"]:
        raise PermissionError("BUILT_IN_ROLE_PROTECTED")
    if not normalized_label:
        raise ValueError("Role label is required")
    with db:
        db.execute("UPDATE roles SET label = ? WHERE key = ?", (normalized_label, role))
        _audit_if_requested(db, actor, "update", "role", role)
    return build_role_response(db, role)


def delete_role(db: sqlite3.Connection, role: str, actor: dict[str, Any] | None = None) -> None:
    row = db.execute("SELECT built_in FROM roles WHERE key = ?", (role,)).fetchone()
    if not row:
        raise KeyError(role)
    if row["built_in"] or role == "super_admin":
        raise PermissionError("BUILT_IN_ROLE_PROTECTED")
    if db.execute("SELECT 1 FROM users WHERE role_key = ? LIMIT 1", (role,)).fetchone():
        raise PermissionError("ROLE_IN_USE")
    with db:
        db.execute("DELETE FROM roles WHERE key = ?", (role,))
        _audit_if_requested(db, actor, "delete", "role", role)


def _normalize_permission_resource(resource: dict[str, Any], *, require_key: bool) -> dict[str, Any]:
    key = str(resource.get("key", "")).strip()
    label = str(resource.get("label", "")).strip()
    description = str(resource.get("description", "")).strip()
    group = str(resource.get("group", "")).strip()
    group_label = str(resource.get("group_label", "")).strip()
    resource_type = str(resource.get("type", "")).strip()
    route = str(resource.get("route", "")).strip() or None
    menu_label = str(resource.get("menu_label", "")).strip() or None
    menu_hint = str(resource.get("menu_hint", "")).strip() or None
    sort = int(resource.get("sort") or 1000)

    if require_key and not PERMISSION_KEY_PATTERN.fullmatch(key):
        raise ValueError("Permission key must use resource:action format with lowercase letters, numbers, and underscores")
    if not label or not description or not group or not group_label:
        raise ValueError("Permission label, description, group, and group label are required")
    if resource_type not in RESOURCE_TYPES:
        raise ValueError("Permission resource type must be menu, button, or api")
    if resource_type == "menu":
        if not route or not menu_label:
            raise ValueError("Menu permission requires route and menu label")
        if not CUSTOM_ROUTE_PATTERN.fullmatch(route):
            raise ValueError("Custom menu route must use /custom/<slug> format")
    else:
        route = None
        menu_label = None
        menu_hint = None

    return {
        "key": key,
        "label": label,
        "description": description,
        "group": group,
        "group_label": group_label,
        "type": resource_type,
        "route": route,
        "menu_label": menu_label,
        "menu_hint": menu_hint,
        "sort": sort,
    }


def create_permission_resource(db: sqlite3.Connection, resource: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    values = _normalize_permission_resource(resource, require_key=True)
    if db.execute("SELECT 1 FROM permission_resources WHERE key = ?", (values["key"],)).fetchone():
        raise KeyError(values["key"])

    with db:
        db.execute(
            """
            INSERT INTO permission_resources
            (key, label, description, group_key, group_label, type, route, menu_label, menu_hint, sort, built_in)
            VALUES (:key, :label, :description, :group, :group_label, :type, :route, :menu_label, :menu_hint, :sort, 0)
            """,
            values,
        )
        _audit_if_requested(db, actor, "create", "permission_resource", values["key"])
    row = db.execute("SELECT * FROM permission_resources WHERE key = ?", (values["key"],)).fetchone()
    return _resource_from_row(row)


def update_permission_resource(db: sqlite3.Connection, key: str, resource: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    row = db.execute("SELECT built_in FROM permission_resources WHERE key = ?", (key,)).fetchone()
    if not row:
        raise KeyError(key)
    if row["built_in"]:
        raise PermissionError("BUILT_IN_PERMISSION_PROTECTED")
    values = _normalize_permission_resource(resource, require_key=False)
    values["key"] = key
    with db:
        db.execute(
            """
            UPDATE permission_resources
            SET label = :label,
                description = :description,
                group_key = :group,
                group_label = :group_label,
                type = :type,
                route = :route,
                menu_label = :menu_label,
                menu_hint = :menu_hint,
                sort = :sort
            WHERE key = :key
            """,
            values,
        )
        _audit_if_requested(db, actor, "update", "permission_resource", key)
    updated = db.execute("SELECT * FROM permission_resources WHERE key = ?", (key,)).fetchone()
    return _resource_from_row(updated)


def delete_permission_resource(db: sqlite3.Connection, key: str, actor: dict[str, Any] | None = None) -> None:
    row = db.execute("SELECT built_in FROM permission_resources WHERE key = ?", (key,)).fetchone()
    if not row:
        raise KeyError(key)
    if row["built_in"]:
        raise PermissionError("BUILT_IN_PERMISSION_PROTECTED")
    if db.execute("SELECT 1 FROM role_permissions WHERE permission_key = ? LIMIT 1", (key,)).fetchone():
        raise PermissionError("PERMISSION_RESOURCE_IN_USE")
    with db:
        db.execute("DELETE FROM permission_resources WHERE key = ?", (key,))
        _audit_if_requested(db, actor, "delete", "permission_resource", key)
