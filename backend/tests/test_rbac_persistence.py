from app.database import get_connection
from app.rbac import list_roles


def test_admin_can_create_role_and_read_it_back(client, admin_token):
    response = client.post(
        "/api/permissions/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"key": "auditor", "label": "审计员", "permissions": ["dashboard:view"]},
    )

    assert response.status_code == 200
    assert response.json()["key"] == "auditor"

    roles_response = client.get("/api/permissions/roles", headers={"Authorization": f"Bearer {admin_token}"})
    assert roles_response.status_code == 200
    assert "auditor" in {role["key"] for role in roles_response.json()}

    with get_connection() as db:
        assert "auditor" in {role["key"] for role in list_roles(db)}


def test_admin_can_create_custom_permission_resource(client, admin_token):
    response = client.post(
        "/api/permissions/resources",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "key": "reports:view",
            "label": "查看报表",
            "description": "查看经营报表",
            "group": "reports",
            "group_label": "报表中心",
            "type": "menu",
            "route": "/custom/reports",
            "menu_label": "报表中心",
            "menu_hint": "经营分析",
        },
    )

    assert response.status_code == 200
    assert response.json()["key"] == "reports:view"

    resources_response = client.get("/api/permissions/resources", headers={"Authorization": f"Bearer {admin_token}"})
    assert resources_response.status_code == 200
    assert "reports:view" in {resource["key"] for resource in resources_response.json()}
