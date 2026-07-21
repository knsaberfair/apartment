def test_viewer_can_access_allowed_read_route(client, viewer_token):
    response = client.get("/api/properties", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["items"]


def test_viewer_cannot_manage_permissions(client, viewer_token):
    response = client.post(
        "/api/permissions/roles",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"key": "auditor", "label": "审计员", "permissions": ["dashboard:view"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_menu_resources_are_limited_to_current_user(client, viewer_token):
    response = client.get("/api/permissions/menus", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert "dashboard:view" in keys
    assert "permissions:view" not in keys
