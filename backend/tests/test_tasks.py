def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_tasks_requires_auth(client):
    response = client.get("/api/tasks")

    assert response.status_code == 401


def test_viewer_cannot_view_tasks(client, viewer_token):
    response = client.get("/api/tasks", headers=auth_headers(viewer_token))

    assert response.status_code == 403


def test_admin_can_view_aggregated_tasks(client, admin_token):
    response = client.get("/api/tasks", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["items"])
    assert body["urgent"] == len([item for item in body["items"] if item["severity"] == "danger"])
    assert {"contracts", "maintenance", "finance", "reconciliation"}.issubset({item["source"] for item in body["items"]})
    assert all(item["id"] == f"{item['source']}:{item['source_id']}" for item in body["items"])


def test_tasks_include_expected_source_statuses(client, admin_token):
    response = client.get("/api/tasks", headers=auth_headers(admin_token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["source"] == "maintenance" and item["status"] != "resolved" for item in items)
    assert any(item["source"] == "contracts" and item["status"] in {"pending", "expiring", "active"} for item in items)
    assert any(item["source"] == "finance" and item["status"] in {"pending", "overdue"} for item in items)
    assert any(item["source"] == "reconciliation" and item["status"] in {"pending", "exception"} for item in items)


def test_tasks_are_limited_to_role_module_permissions(client):
    role_sources = {
        "leasing": {"contracts"},
        "maintenance": {"maintenance"},
        "finance": {"contracts", "finance", "reconciliation"},
    }

    for username, expected_sources in role_sources.items():
        token_response = client.post("/api/auth/login", json={"username": username, "password": f"{username}123"})
        assert token_response.status_code == 200

        response = client.get("/api/tasks", headers=auth_headers(token_response.json()["access_token"]))

        assert response.status_code == 200
        sources = {item["source"] for item in response.json()["items"]}
        assert sources == expected_sources


def test_disallowed_source_filter_returns_no_tasks(client):
    token_response = client.post("/api/auth/login", json={"username": "leasing", "password": "leasing123"})
    assert token_response.status_code == 200

    response = client.get("/api/tasks?source=finance", headers=auth_headers(token_response.json()["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_confirmed_finance_transaction_disappears_from_tasks(client):
    token_response = client.post("/api/auth/login", json={"username": "finance", "password": "finance123"})
    assert token_response.status_code == 200
    headers = auth_headers(token_response.json()["access_token"])
    tasks_response = client.get("/api/tasks", headers=headers)
    assert tasks_response.status_code == 200
    finance_task = next(item for item in tasks_response.json()["items"] if item["source"] == "finance")

    confirm_response = client.post(f"/api/finance/transactions/{finance_task['source_id']}/confirm", headers=headers)
    refreshed_response = client.get("/api/tasks", headers=headers)

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "paid"
    assert refreshed_response.status_code == 200
    assert all(item["id"] != finance_task["id"] for item in refreshed_response.json()["items"])


def test_reviewed_reconciliation_record_disappears_from_tasks(client):
    token_response = client.post("/api/auth/login", json={"username": "finance", "password": "finance123"})
    assert token_response.status_code == 200
    headers = auth_headers(token_response.json()["access_token"])
    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-TASK-EXCEPTION",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-TASK-EXCEPTION",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19000,
                    "channel": "支付宝",
                }
            ]
        },
    )
    assert import_response.status_code == 200

    resolve_response = client.post("/api/finance/reconciliation/R-TASK-EXCEPTION/resolve", headers=headers)
    refreshed_response = client.get("/api/tasks", headers=headers)

    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "reviewed"
    assert refreshed_response.status_code == 200
    assert all(item["id"] != "reconciliation:R-TASK-EXCEPTION" for item in refreshed_response.json()["items"])


def test_retry_matched_reconciliation_record_disappears_from_tasks(client):
    from app.database import get_connection

    token_response = client.post("/api/auth/login", json={"username": "finance", "password": "finance123"})
    assert token_response.status_code == 200
    headers = auth_headers(token_response.json()["access_token"])

    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-TASK-RETRY",
                    "date": "2026-07-15",
                    "bank_flow_id": "BK-TASK-RETRY",
                    "system_flow_id": "F-TASK-RETRY",
                    "payer": "林思远",
                    "amount": 6800,
                    "channel": "银行转账",
                }
            ]
        },
    )
    assert import_response.status_code == 200
    assert import_response.json()[0]["status"] == "pending"

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-TASK-RETRY", "P-1201", "2026-07-15", "租金收入", "A-1201", "林思远", 6800, "银行转账", "paid", "测试"),
        )

    retry_response = client.post("/api/finance/reconciliation/R-TASK-RETRY/retry-match", headers=headers)
    refreshed_response = client.get("/api/tasks", headers=headers)

    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "matched"
    assert refreshed_response.status_code == 200
    assert all(item["id"] != "reconciliation:R-TASK-RETRY" for item in refreshed_response.json()["items"])


def test_move_out_pending_settlement_enters_and_leaves_tasks(client, admin_token):
    headers = auth_headers(admin_token)
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out_id = move_out_response.json()["id"]

    tasks_response = client.get("/api/tasks", headers=headers)
    assert tasks_response.status_code == 200
    assert any(item["id"] == f"contracts:move_out:{move_out_id}" for item in tasks_response.json()["items"])

    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out_id}/settle",
        headers=headers,
        json={"deductions": 0, "settled_date": "2026-08-02"},
    )
    assert settlement_response.status_code == 200

    refreshed_response = client.get("/api/tasks", headers=headers)
    assert refreshed_response.status_code == 200
    assert all(item["id"] != f"contracts:move_out:{move_out_id}" for item in refreshed_response.json()["items"])
