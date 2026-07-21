from app.database import get_connection
from app.security import hash_password


ROLE_PAYLOAD = {"key": "auditor", "label": "审计员", "permissions": ["dashboard:view"]}
RESOURCE_PAYLOAD = {
    "key": "reports:view",
    "label": "查看报表",
    "description": "查看经营报表",
    "group": "reports",
    "group_label": "报表中心",
    "type": "menu",
    "route": "/custom/reports",
    "menu_label": "报表中心",
    "menu_hint": "经营分析",
}


def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def create_custom_role(client, admin_token):
    response = client.post("/api/permissions/roles", headers=admin_headers(admin_token), json=ROLE_PAYLOAD)
    assert response.status_code == 200
    return response.json()


def create_custom_resource(client, admin_token):
    response = client.post("/api/permissions/resources", headers=admin_headers(admin_token), json=RESOURCE_PAYLOAD)
    assert response.status_code == 200
    return response.json()


def test_custom_role_can_be_renamed_and_deleted(client, admin_token):
    create_custom_role(client, admin_token)

    update_response = client.put("/api/permissions/roles/auditor", headers=admin_headers(admin_token), json={"label": "高级审计员"})
    delete_response = client.delete("/api/permissions/roles/auditor", headers=admin_headers(admin_token))
    roles_response = client.get("/api/permissions/roles", headers=admin_headers(admin_token))

    assert update_response.status_code == 200
    assert update_response.json()["label"] == "高级审计员"
    assert update_response.json()["built_in"] is False
    assert delete_response.status_code == 204
    assert "auditor" not in {role["key"] for role in roles_response.json()}


def test_builtin_role_cannot_be_renamed_or_deleted(client, admin_token):
    headers = admin_headers(admin_token)

    rename_response = client.put("/api/permissions/roles/manager", headers=headers, json={"label": "x"})
    delete_response = client.delete("/api/permissions/roles/manager", headers=headers)

    assert rename_response.status_code == 409
    assert rename_response.json()["detail"]["code"] == "BUILT_IN_ROLE_PROTECTED"
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"]["code"] == "BUILT_IN_ROLE_PROTECTED"



def test_super_admin_role_permissions_can_be_updated(client, admin_token):
    headers = admin_headers(admin_token)

    response = client.put("/api/permissions/roles/super_admin/permissions", headers=headers, json={"permissions": ["dashboard:view"]})

    assert response.status_code == 200
    assert response.json()["key"] == "super_admin"
    assert response.json()["permissions"] == ["dashboard:view"]


def test_manager_builtin_role_permissions_can_be_updated(client, admin_token):
    headers = admin_headers(admin_token)

    response = client.put("/api/permissions/roles/manager/permissions", headers=headers, json={"permissions": ["dashboard:view"]})

    assert response.status_code == 200
    assert response.json()["key"] == "manager"
    assert response.json()["permissions"] == ["dashboard:view"]


def test_role_used_by_user_cannot_be_deleted(client, admin_token):
    create_custom_role(client, admin_token)
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            ("auditor-user", "auditor", "审计员", hash_password("audit123"), "auditor", "2026-07-15T00:00:00+00:00"),
        )
        db.commit()

    response = client.delete("/api/permissions/roles/auditor", headers=admin_headers(admin_token))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ROLE_IN_USE"


def test_custom_permission_resource_can_be_updated_and_deleted(client, admin_token):
    create_custom_resource(client, admin_token)

    update_response = client.put(
        "/api/permissions/resources/reports:view",
        headers=admin_headers(admin_token),
        json={**RESOURCE_PAYLOAD, "label": "查看经营报表", "description": "查看经营统计报表"},
    )
    delete_response = client.delete("/api/permissions/resources/reports:view", headers=admin_headers(admin_token))
    resources_response = client.get("/api/permissions/resources", headers=admin_headers(admin_token))

    assert update_response.status_code == 200
    assert update_response.json()["label"] == "查看经营报表"
    assert update_response.json()["built_in"] is False
    assert delete_response.status_code == 204
    assert "reports:view" not in {resource["key"] for resource in resources_response.json()}


def test_assigned_custom_permission_resource_cannot_be_deleted(client, admin_token):
    create_custom_resource(client, admin_token)
    create_response = client.post(
        "/api/permissions/roles",
        headers=admin_headers(admin_token),
        json={"key": "report_viewer", "label": "报表查看员", "permissions": ["reports:view"]},
    )
    assert create_response.status_code == 200

    response = client.delete("/api/permissions/resources/reports:view", headers=admin_headers(admin_token))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PERMISSION_RESOURCE_IN_USE"


def test_update_permission_resource_does_not_accept_body_key(client, admin_token):
    create_custom_resource(client, admin_token)
    payload = {**RESOURCE_PAYLOAD, "key": "other:view", "label": "查看经营报表"}

    response = client.put("/api/permissions/resources/reports:view", headers=admin_headers(admin_token), json=payload)

    assert response.status_code == 200
    assert response.json()["key"] == "reports:view"
    assert response.json()["label"] == "查看经营报表"


def test_builtin_permission_resource_cannot_be_updated_or_deleted(client, admin_token):
    headers = admin_headers(admin_token)
    payload = {
        **RESOURCE_PAYLOAD,
        "key": "dashboard:view",
        "label": "查看控制台",
        "description": "x",
        "group": "dashboard",
        "group_label": "管理控制台",
        "type": "menu",
        "route": "/custom/dashboard",
        "menu_label": "控制台",
    }

    update_response = client.put("/api/permissions/resources/dashboard:view", headers=headers, json=payload)
    delete_response = client.delete("/api/permissions/resources/dashboard:view", headers=headers)

    assert update_response.status_code == 409
    assert update_response.json()["detail"]["code"] == "BUILT_IN_PERMISSION_PROTECTED"
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"]["code"] == "BUILT_IN_PERMISSION_PROTECTED"
