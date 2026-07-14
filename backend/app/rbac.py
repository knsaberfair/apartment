from typing import Any

ALL_PERMISSIONS = {
    "dashboard:view",
    "dashboard:export",
    "properties:view",
    "properties:create",
    "properties:update",
    "properties:delete",
    "tenants:view",
    "tenants:create",
    "tenants:update",
    "tenants:delete",
    "contracts:view",
    "contracts:create",
    "contracts:approve",
    "contracts:terminate",
    "maintenance:view",
    "maintenance:create",
    "maintenance:assign",
    "maintenance:resolve",
    "finance:view",
    "finance:create",
    "finance:export",
    "reconciliation:view",
    "reconciliation:import",
    "reconciliation:export",
    "system:settings",
    "tasks:view",
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
    "manager": ALL_PERMISSIONS - {"system:settings"},
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
