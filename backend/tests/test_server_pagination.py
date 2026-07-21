def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_page_shape(body: dict, limit: int, offset: int) -> None:
    assert set(body) >= {"items", "total", "limit", "offset"}
    assert body["limit"] == limit
    assert body["offset"] == offset
    assert isinstance(body["items"], list)
    assert body["total"] >= len(body["items"])


def assert_endpoint_paginates(client, admin_token, path: str) -> None:
    headers = auth_headers(admin_token)
    first_page = client.get(f"{path}?limit=2&offset=0", headers=headers)
    second_page = client.get(f"{path}?limit=2&offset=2", headers=headers)

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first_body = first_page.json()
    second_body = second_page.json()
    assert_page_shape(first_body, 2, 0)
    assert_page_shape(second_body, 2, 2)
    assert len(first_body["items"]) <= 2
    assert len(second_body["items"]) <= 2
    if second_body["items"]:
        assert {repr(item) for item in first_body["items"]}.isdisjoint({repr(item) for item in second_body["items"]})


def test_main_list_endpoints_paginate(client, admin_token):
    for path in (
        "/api/properties",
        "/api/tenants",
        "/api/contracts",
        "/api/maintenance-orders",
        "/api/finance/transactions",
        "/api/finance/reconciliation",
    ):
        assert_endpoint_paginates(client, admin_token, path)


def test_main_list_endpoints_support_search(client, admin_token):
    headers = auth_headers(admin_token)
    cases = (
        ("/api/properties", "P-1201"),
        ("/api/tenants", "林思远"),
        ("/api/contracts", "C-2026-0318"),
        ("/api/maintenance-orders", "M-240713-08"),
        ("/api/finance/transactions", "F-20260714-002"),
        ("/api/finance/reconciliation", "BK202607140091"),
    )
    for path, keyword in cases:
        response = client.get(f"{path}?q={keyword}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert body["items"]


def test_tasks_support_pagination_and_search(client, admin_token):
    headers = auth_headers(admin_token)
    first_page = client.get("/api/tasks?limit=2&offset=0", headers=headers)
    second_page = client.get("/api/tasks?limit=2&offset=2", headers=headers)
    filtered = client.get("/api/tasks?q=合同", headers=headers)

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert_page_shape(first_page.json(), 2, 0)
    assert_page_shape(second_page.json(), 2, 2)
    assert first_page.json()["total"] >= len(first_page.json()["items"])
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert filtered.json()["items"]


def test_tasks_support_source_and_severity_filters(client, admin_token):
    headers = auth_headers(admin_token)
    response = client.get("/api/tasks?source=maintenance&severity=danger&limit=20", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert_page_shape(body, 20, 0)
    assert body["total"] >= len(body["items"])
    assert body["urgent"] == body["total"]
    assert all(item["source"] == "maintenance" and item["severity"] == "danger" for item in body["items"])
