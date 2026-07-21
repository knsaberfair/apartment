from datetime import date, timedelta

from app.database import get_connection

TENANT_ID = "T-10001"
BIND_CODE = "tenant-bind-code"
DISPLAY_NAME = "林思远"
PAYABLE_BILL_ID = "F-20260720-001"
REPAIR_TITLE = "空调异响"
REPAIR_CATEGORY = "家电"
REPAIR_PRIORITY = "high"
REPAIR_DUE_DATE = (date.today() + timedelta(days=7)).isoformat()


def _bind_tenant(client):
    response = client.post(
        "/api/tenant/auth/bind",
        json={
            "tenant_id": TENANT_ID,
            "code": BIND_CODE,
            "display_name": DISPLAY_NAME,
        },
    )
    assert response.status_code == 200
    return response.json()


def _login_tenant(client):
    response = client.post("/api/tenant/auth/login", json={"code": BIND_CODE})
    if response.status_code == 401:
        _bind_tenant(client)
        response = client.post("/api/tenant/auth/login", json={"code": BIND_CODE})
    assert response.status_code == 200
    return response.json()


def test_tenant_bind_login_and_profile(client):
    bind_body = _bind_tenant(client)
    login_body = _login_tenant(client)

    assert bind_body["token_type"] == "bearer"
    assert login_body["token_type"] == "bearer"
    assert bind_body["profile"]["id"] == TENANT_ID
    assert bind_body["profile"]["display_name"] == DISPLAY_NAME
    assert bind_body["profile"]["account_id"] == "TA-T-10001"
    assert login_body["profile"]["room"] == "A-1201"

    profile_response = client.get(
        "/api/tenant/profile",
        headers={"Authorization": f"Bearer {login_body['access_token']}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["contract_id"] == "C-2026-0318"


def test_tenant_home_and_lists_are_scoped(client):
    login_body = _login_tenant(client)
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}

    home_response = client.get("/api/tenant/home", headers=headers)
    assert home_response.status_code == 200
    home = home_response.json()
    assert home["contract_count"] == 1
    assert home["bill_count"] == 1
    assert home["repair_count"] == 1
    assert home["recent_contracts"][0]["id"] == "C-2026-0318"
    assert home["recent_bills"][0]["id"] == "F-20260714-001"
    assert home["recent_repairs"][0]["id"] == "M-240712-03"

    contracts_response = client.get("/api/tenant/contracts", headers=headers)
    bills_response = client.get("/api/tenant/bills", headers=headers)
    repairs_response = client.get("/api/tenant/repairs", headers=headers)

    assert contracts_response.status_code == 200
    assert bills_response.status_code == 200
    assert repairs_response.status_code == 200
    assert [item["id"] for item in contracts_response.json()] == ["C-2026-0318"]
    assert [item["id"] for item in bills_response.json()] == ["F-20260714-001"]
    assert [item["id"] for item in repairs_response.json()] == ["M-240712-03"]


def test_tenant_can_pay_bill(client):
    login_body = _login_tenant(client)
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (PAYABLE_BILL_ID, "P-1201", date.today().isoformat(), "租金收入", "A-1201", DISPLAY_NAME, 6800, "待支付", "pending", "租户端待支付账单", "C-2026-0318"),
        )

    response = client.post(f"/api/tenant/bills/{PAYABLE_BILL_ID}/pay", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == PAYABLE_BILL_ID
    assert body["status"] == "paid"
    assert body["method"] == "微信支付"

    bills_response = client.get("/api/tenant/bills", headers=headers)
    assert bills_response.status_code == 200
    paid_bill = next(item for item in bills_response.json() if item["id"] == PAYABLE_BILL_ID)
    assert paid_bill["status"] == "paid"


def test_tenant_can_create_repair(client):
    login_body = _login_tenant(client)
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}

    response = client.post(
        "/api/tenant/repairs",
        headers=headers,
        json={
            "title": REPAIR_TITLE,
            "category": REPAIR_CATEGORY,
            "priority": REPAIR_PRIORITY,
            "due_at": REPAIR_DUE_DATE,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == REPAIR_TITLE
    assert body["category"] == REPAIR_CATEGORY
    assert body["priority"] == REPAIR_PRIORITY
    assert body["status"] == "open"
    assert body["assignee"] == "未分配"
    assert body["property_id"] == "P-1201"
    assert body["tenant"] == DISPLAY_NAME
    assert body["due_at"] == REPAIR_DUE_DATE

    repairs_response = client.get("/api/tenant/repairs", headers=headers)
    assert repairs_response.status_code == 200
    assert any(item["title"] == REPAIR_TITLE for item in repairs_response.json())


def test_tenant_cannot_rebind_existing_account_to_another_openid(client):
    _bind_tenant(client)

    response = client.post(
        "/api/tenant/auth/bind",
        json={
            "tenant_id": TENANT_ID,
            "code": "different-wechat-code",
            "display_name": DISPLAY_NAME,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_ACCOUNT_ALREADY_BOUND"


def test_tenant_mock_bind_can_recover_after_stale_binding(client):
    _bind_tenant(client)
    dev_code = f"tenant-dev-{TENANT_ID}"

    login_response = client.post("/api/tenant/auth/login", json={"code": dev_code})
    assert login_response.status_code == 401

    bind_response = client.post(
        "/api/tenant/auth/bind",
        json={
            "tenant_id": TENANT_ID,
            "code": dev_code,
            "display_name": DISPLAY_NAME,
        },
    )

    assert bind_response.status_code == 200
    body = bind_response.json()
    assert body["profile"]["id"] == TENANT_ID
    assert body["profile"]["display_name"] == DISPLAY_NAME

    login_response = client.post("/api/tenant/auth/login", json={"code": dev_code})
    assert login_response.status_code == 200


def test_tenant_bills_do_not_include_other_room_occupants(client):
    login_body = _login_tenant(client)
    headers = {"Authorization": f"Bearer {login_body['access_token']}"}
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-OTHER-TENANT", "P-1201", date.today().isoformat(), "租金收入", "A-1201", "历史租客", 6800, "待支付", "pending", "历史租客账单"),
        )

    bills_response = client.get("/api/tenant/bills", headers=headers)
    assert bills_response.status_code == 200
    assert "F-OTHER-TENANT" not in [item["id"] for item in bills_response.json()]

    pay_response = client.post("/api/tenant/bills/F-OTHER-TENANT/pay", headers=headers)
    assert pay_response.status_code == 404
    assert pay_response.json()["detail"]["code"] == "FINANCE_TRANSACTION_NOT_FOUND"


def test_tenant_token_cannot_access_staff_routes(client):
    login_body = _login_tenant(client)
    response = client.get(
        "/api/properties",
        headers={"Authorization": f"Bearer {login_body['access_token']}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"
