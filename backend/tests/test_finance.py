import hashlib

from app.database import get_connection


def expected_rent_bill_id(contract_id: str, month: str) -> str:
    digest = hashlib.sha256(f"{contract_id}\0{month}".encode("utf-8")).hexdigest()[:16].upper()
    return f"RENT-{month.replace('-', '')}-{digest}"


def finance_headers(client):
    response = client.post("/api/auth/login", json={"username": "finance", "password": "finance123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


TRANSACTION_PAYLOAD = {
    "id": "F-TEST-001",
    "property_id": "P-1201",
    "date": "2026-07-15",
    "type": "租金收入",
    "tenant": "林思远",
    "amount": 6800,
    "method": "银行转账",
    "status": "paid",
    "note": "测试流水",
}


def test_finance_staff_can_create_and_export_transaction(client):
    headers = finance_headers(client)

    create_response = client.post("/api/finance/transactions", headers=headers, json=TRANSACTION_PAYLOAD)
    export_response = client.get("/api/finance/transactions/export", headers=headers)

    assert create_response.status_code == 200
    assert create_response.json()["room"] == "A-1201"
    assert create_response.json()["tenant"] == "林思远"
    assert export_response.status_code == 200
    assert "text/csv" in export_response.headers["content-type"]
    assert "F-TEST-001" in export_response.text
    assert "contract_id" in export_response.text
    assert "settlement_id" in export_response.text
    assert "lifecycle_type" in export_response.text
    with get_connection() as db:
        audit_row = db.execute(
            "SELECT 1 FROM audit_logs WHERE action = ? AND resource_type = ? AND resource_id = ?",
            ("export", "finance_transaction", "all"),
        ).fetchone()
    assert audit_row is not None


def test_viewer_cannot_create_or_export_transaction(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    create_response = client.post("/api/finance/transactions", headers=headers, json=TRANSACTION_PAYLOAD)
    export_response = client.get("/api/finance/transactions/export", headers=headers)

    assert create_response.status_code == 403
    assert export_response.status_code == 403


def test_export_permissions_require_matching_view_permission(client):
    from app.security import hash_password

    with get_connection() as db:
        db.execute("INSERT INTO roles (key, label, built_in) VALUES (?, ?, 0)", ("finance_export_only", "仅导出财务"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("finance_export_only", "finance:export"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("finance_export_only", "reconciliation:export"))
        db.execute(
            """
            INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            ("finance-export-only-user", "finance_export_only", "仅导出财务", hash_password("export123"), "finance_export_only", "2026-07-15T00:00:00+00:00"),
        )
        db.commit()

    token_response = client.post("/api/auth/login", json={"username": "finance_export_only", "password": "export123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    assert client.get("/api/finance/transactions/export", headers=headers).status_code == 403
    assert client.get("/api/finance/reconciliation/export", headers=headers).status_code == 403
    assert client.get("/api/finance/settlements/export", headers=headers).status_code == 403


def test_finance_staff_can_generate_rent_bills(client):
    response = client.post("/api/finance/rent-bills/generate", headers=finance_headers(client), json={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-07"
    assert body["created"] == 3
    assert body["skipped"] == 0
    bill_id = expected_rent_bill_id("C-2026-0318", "2026-07")
    bills = {item["id"]: item for item in body["transactions"]}
    assert bills[bill_id]["type"] == "租金账单"
    assert bills[bill_id]["property_id"] == "P-1201"
    assert bills[bill_id]["room"] == "A-1201"
    assert bills[bill_id]["tenant"] == "林思远"
    assert bills[bill_id]["amount"] == 6800
    assert bills[bill_id]["date"] == "2026-07-18"
    assert bills[bill_id]["status"] == "overdue"
    assert bills[bill_id]["note"] == "自动生成租金账单；合同编号=C-2026-0318；账期=2026-07"
    assert bills[bill_id]["contract_id"] == "C-2026-0318"
    assert bills[bill_id]["lifecycle_type"] == "rent"


def test_generate_rent_bills_is_idempotent(client):
    headers = finance_headers(client)

    first_response = client.post("/api/finance/rent-bills/generate", headers=headers, json={"month": "2026-07"})
    second_response = client.post("/api/finance/rent-bills/generate", headers=headers, json={"month": "2026-07"})
    transactions_response = client.get("/api/finance/transactions", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["created"] == 3
    assert second_response.json()["created"] == 0
    assert second_response.json()["skipped"] == 3
    generated_ids = [item["id"] for item in transactions_response.json()["items"] if item["id"].startswith("RENT-")]
    assert sorted(generated_ids) == sorted(
        [
            expected_rent_bill_id("C-2025-0822", "2026-07"),
            expected_rent_bill_id("C-2026-0110", "2026-07"),
            expected_rent_bill_id("C-2026-0318", "2026-07"),
        ]
    )


def test_viewer_cannot_generate_rent_bills(client, viewer_token):
    response = client.post("/api/finance/rent-bills/generate", headers={"Authorization": f"Bearer {viewer_token}"}, json={"month": "2026-07"})

    assert response.status_code == 403


def test_generate_rent_bills_uses_non_lossy_ids_for_similar_contracts(client):
    headers = finance_headers(client)
    with get_connection() as db:
        db.executemany(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("P-EDGE-1", "E 栋", "0101", "E-0101", "一室一厅", 40, 1000, "vacant", None, None, "[]"),
                ("P-EDGE-2", "E 栋", "0102", "E-0102", "一室一厅", 40, 1000, "vacant", None, None, "[]"),
            ],
        )
        db.execute(
            """
            INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C/EDGE", "P-EDGE-1", "边界租客一", "E-0101", "2026-07-01", "2026-12-31", 1000, 1000, "pending", 168),
        )
        db.execute(
            """
            INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C-EDGE", "P-EDGE-2", "边界租客二", "E-0102", "2026-07-01", "2026-12-31", 1000, 1000, "pending", 168),
        )
        db.execute("UPDATE contracts SET status = 'active' WHERE id IN (?, ?)", ("C/EDGE", "C-EDGE"))
        db.commit()

    response = client.post("/api/finance/rent-bills/generate", headers=headers, json={"month": "2026-07"})

    assert response.status_code == 200
    generated_ids = {item["id"] for item in response.json()["transactions"]}
    assert expected_rent_bill_id("C/EDGE", "2026-07") in generated_ids
    assert expected_rent_bill_id("C-EDGE", "2026-07") in generated_ids


def test_create_transaction_rejects_reserved_rent_bill_prefix(client):
    response = client.post(
        "/api/finance/transactions",
        headers=finance_headers(client),
        json={**TRANSACTION_PAYLOAD, "id": "RENT-MANUAL-001"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "RESERVED_FINANCE_TRANSACTION_ID"


def test_create_transaction_rejects_lifecycle_metadata(client):
    headers = finance_headers(client)
    for field, value in (("contract_id", "C-2026-0318"), ("settlement_id", "SETTLE-1"), ("lifecycle_type", "rent")):
        response = client.post(
            "/api/finance/transactions",
            headers=headers,
            json={**TRANSACTION_PAYLOAD, "id": f"F-META-{field}", field: value},
        )

        assert response.status_code == 422


def test_database_rejects_manual_reserved_finance_prefix_without_lifecycle_metadata():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("RENT-MANUAL-DB", "P-1201", "2026-07-01", "手工账单", "A-1201", "林思远", 1, "银行转账", "paid", "手工占用编号"),
            )
        except Exception as exc:
            assert "RESERVED_FINANCE_TRANSACTION_ID" in str(exc)
        else:
            raise AssertionError("reserved finance prefix should be blocked by database")


def test_generate_rent_bills_rejects_unrelated_transaction_id_conflict(client, monkeypatch):
    headers = finance_headers(client)
    bill_id = "RENT-COLLISION"
    monkeypatch.setattr("app.repositories._rent_bill_id", lambda contract_id, month: bill_id)
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, lifecycle_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bill_id, "P-1201", "2026-07-01", "手工账单", "A-1201", "林思远", 1, "银行转账", "paid", "手工占用编号", "OTHER-CONTRACT", "rent"),
        )
        db.commit()

    response = client.post("/api/finance/rent-bills/generate", headers=headers, json={"month": "2026-07"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "FINANCE_TRANSACTION_ALREADY_EXISTS"


def test_generate_rent_bills_rejects_invalid_month(client):
    response = client.post("/api/finance/rent-bills/generate", headers=finance_headers(client), json={"month": "2026-7"})

    assert response.status_code == 422


def test_generated_overdue_rent_bill_enters_and_leaves_tasks(client):
    headers = finance_headers(client)

    generate_response = client.post("/api/finance/rent-bills/generate", headers=headers, json={"month": "2026-06"})
    tasks_response = client.get("/api/tasks", headers=headers)
    bill_id = expected_rent_bill_id("C-2026-0318", "2026-06")
    confirm_response = client.post(f"/api/finance/transactions/{bill_id}/confirm", headers=headers)
    refreshed_tasks_response = client.get("/api/tasks", headers=headers)

    assert generate_response.status_code == 200
    bill = next(item for item in generate_response.json()["transactions"] if item["id"] == bill_id)
    assert bill["status"] == "overdue"
    assert tasks_response.status_code == 200
    task = next(item for item in tasks_response.json()["items"] if item["id"] == f"finance:{bill_id}")
    assert task["severity"] == "danger"
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "paid"
    assert refreshed_tasks_response.status_code == 200
    assert all(item["id"] != f"finance:{bill_id}" for item in refreshed_tasks_response.json()["items"])


def test_create_transaction_for_missing_property_returns_not_found(client):
    response = client.post(
        "/api/finance/transactions",
        headers=finance_headers(client),
        json={**TRANSACTION_PAYLOAD, "property_id": "missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_create_transaction_rejects_reconciled_status(client):
    response = client.post(
        "/api/finance/transactions",
        headers=finance_headers(client),
        json={**TRANSACTION_PAYLOAD, "status": "reconciled"},
    )

    assert response.status_code == 422


def test_create_transaction_rejects_zero_amount(client):
    response = client.post(
        "/api/finance/transactions",
        headers=finance_headers(client),
        json={**TRANSACTION_PAYLOAD, "amount": 0},
    )

    assert response.status_code == 422


def test_reconciliation_import_matches_transaction_and_marks_reconciled(client):
    headers = finance_headers(client)
    confirm_response = client.post("/api/finance/transactions/F-20260714-002/confirm", headers=headers)
    assert confirm_response.status_code == 200

    response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-TEST-MATCH",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-TEST-MATCH",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )
    transactions_response = client.get("/api/finance/transactions", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "matched"
    assert response.json()[0]["difference"] == 0
    matched_transaction = next(item for item in transactions_response.json()["items"] if item["id"] == "F-20260714-002")
    assert matched_transaction["status"] == "reconciled"


def test_reconciliation_import_detects_amount_exception(client):
    response = client.post(
        "/api/finance/reconciliation/import",
        headers=finance_headers(client),
        json={
            "records": [
                {
                    "id": "R-TEST-EXCEPTION",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-TEST-EXCEPTION",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19000,
                    "channel": "支付宝",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["status"] == "exception"
    assert response.json()[0]["difference"] == -200


def test_reconciliation_import_marks_missing_system_flow_pending(client):
    response = client.post(
        "/api/finance/reconciliation/import",
        headers=finance_headers(client),
        json={
            "records": [
                {
                    "id": "R-TEST-PENDING",
                    "date": "2026-07-15",
                    "bank_flow_id": "BK-TEST-PENDING",
                    "system_flow_id": "missing",
                    "payer": "未知付款方",
                    "amount": 1000,
                    "channel": "银行",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["status"] == "pending"
    assert response.json()[0]["difference"] == 0


def test_viewer_cannot_import_or_export_reconciliation(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    payload = {
        "records": [
            {
                "id": "R-VIEWER",
                "date": "2026-07-15",
                "bank_flow_id": "BK-VIEWER",
                "system_flow_id": "F-20260714-001",
                "payer": "林思远",
                "amount": 6800,
                "channel": "招商银行",
            }
        ]
    }

    import_response = client.post("/api/finance/reconciliation/import", headers=headers, json=payload)
    export_response = client.get("/api/finance/reconciliation/export", headers=headers)

    assert import_response.status_code == 403
    assert export_response.status_code == 403


def test_finance_staff_can_export_reconciliation(client):
    response = client.get("/api/finance/reconciliation/export", headers=finance_headers(client))

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "R-001" in response.text
    with get_connection() as db:
        audit_row = db.execute(
            "SELECT 1 FROM audit_logs WHERE action = ? AND resource_type = ? AND resource_id = ?",
            ("export", "reconciliation", "all"),
        ).fetchone()
    assert audit_row is not None


def test_csv_export_escapes_whitespace_prefixed_formulas(client):
    from app.database import get_connection

    headers = finance_headers(client)
    with get_connection() as db:
        db.execute(
            """
            UPDATE finance_transactions
            SET type = ?
            WHERE id = ?
            """,
            (' \t=HYPERLINK("http://example.invalid")', "F-20260714-002"),
        )
    export_response = client.get("/api/finance/transactions/export", headers=headers)

    assert export_response.status_code == 200
    assert "' \t=HYPERLINK" in export_response.text


def test_duplicate_reconciliation_system_flow_is_rejected(client):
    headers = finance_headers(client)
    confirm_response = client.post("/api/finance/transactions/F-20260714-002/confirm", headers=headers)
    assert confirm_response.status_code == 200

    first = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-DUP-A",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-DUP-A",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )
    second = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-DUP-B",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-DUP-B",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "RECONCILIATION_FLOW_ALREADY_EXISTS"


def test_weak_reconciliation_match_is_not_marked_matched(client):
    headers = finance_headers(client)
    response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-WEAK-MATCH",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-WEAK-MATCH",
                    "system_flow_id": "F-20260714-002",
                    "payer": "其他付款方",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )
    transactions_response = client.get("/api/finance/transactions", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "exception"
    transaction = next(item for item in transactions_response.json()["items"] if item["id"] == "F-20260714-002")
    assert transaction["status"] == "pending"


def test_direct_invalid_reconciliation_insert_is_blocked_by_database_trigger():
    import sqlite3

    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("R-BAD-DIRECT", "2026-02-30", "BK-BAD", "F-BAD", "测试", 100, "银行", "matched", 10),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_RECONCILIATION_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid reconciliation insert should be blocked")


def test_direct_invalid_finance_insert_is_blocked_by_database_trigger():
    import sqlite3

    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("F-BAD-DIRECT", "P-1201", "2026-02-30", "x" * 41, "A-1201", "林思远", 100, "银行", "reconciled", "测试"),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_FINANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid finance insert should be blocked")


def test_direct_false_matched_reconciliation_is_blocked_by_database_trigger():
    import sqlite3

    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("R-FALSE-MATCH", "2026-07-14", "BK-FALSE-MATCH", "F-20260714-002", "其他付款方", 19200, "支付宝", "matched", 0),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_RECONCILIATION_PAYLOAD" in str(exc)
        else:
            raise AssertionError("false matched reconciliation should be blocked")


def test_direct_reconciled_transaction_update_is_blocked_by_database_trigger(client):
    import sqlite3

    from app.database import get_connection

    confirm_response = client.post("/api/finance/transactions/F-20260714-002/confirm", headers=finance_headers(client))
    assert confirm_response.status_code == 200

    response = client.post(
        "/api/finance/reconciliation/import",
        headers=finance_headers(client),
        json={
            "records": [
                {
                    "id": "R-DIRECT-MATCH",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-DIRECT-MATCH",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )
    assert response.status_code == 200

    with get_connection() as db:
        try:
            db.execute("UPDATE finance_transactions SET amount = ? WHERE id = ?", (1, "F-20260714-002"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_FINANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("matched reconciled transaction update should be blocked")

        for column, value in (
            ("type", "其他收入"),
            ("property_id", "P-0806"),
            ("room", "B-0806"),
            ("note", "篡改备注"),
            ("status", "paid"),
        ):
            try:
                db.execute(f"UPDATE finance_transactions SET {column} = ? WHERE id = ?", (value, "F-20260714-002"))
            except sqlite3.DatabaseError as exc:
                assert "INVALID_FINANCE_PAYLOAD" in str(exc)
            else:
                raise AssertionError(f"reconciled transaction {column} update should be blocked")


def test_direct_valid_matched_reconciliation_syncs_transaction_status(client):
    from app.database import get_connection

    confirm_response = client.post("/api/finance/transactions/F-20260714-002/confirm", headers=finance_headers(client))
    assert confirm_response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("R-DIRECT-SYNC", "2026-07-14", "BK-DIRECT-SYNC", "F-20260714-002", "赵安琪", 19200, "支付宝", "matched", 0),
        )
        transaction = db.execute("SELECT status FROM finance_transactions WHERE id = ?", ("F-20260714-002",)).fetchone()

    assert transaction["status"] == "reconciled"


def test_direct_matched_reconciliation_is_immutable():
    import sqlite3

    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("UPDATE reconciliation_records SET status = ? WHERE id = ?", ("exception", "R-001"))
        except sqlite3.DatabaseError as exc:
            assert "RECONCILIATION_MATCHED_IMMUTABLE" in str(exc)
        else:
            raise AssertionError("matched reconciliation update should be blocked")

        try:
            db.execute("DELETE FROM reconciliation_records WHERE id = ?", ("R-001",))
        except sqlite3.DatabaseError as exc:
            assert "RECONCILIATION_MATCHED_IMMUTABLE" in str(exc)
        else:
            raise AssertionError("matched reconciliation delete should be blocked")


def test_direct_reconciled_transaction_delete_is_blocked_by_database_trigger():
    import sqlite3

    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("DELETE FROM finance_transactions WHERE id = ?", ("F-20260714-001",))
        except sqlite3.DatabaseError as exc:
            assert "FINANCE_TRANSACTION_DELETE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("reconciled transaction delete should be blocked")


def test_direct_reconciled_transaction_reference_delete_is_blocked_by_database_trigger(client):
    import sqlite3

    from app.database import get_connection

    response = client.post(
        "/api/finance/reconciliation/import",
        headers=finance_headers(client),
        json={
            "records": [
                {
                    "id": "R-DELETE-BLOCK",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-DELETE-BLOCK",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19200,
                    "channel": "支付宝",
                }
            ]
        },
    )
    assert response.status_code == 200

    with get_connection() as db:
        try:
            db.execute("DELETE FROM finance_transactions WHERE id = ?", ("F-20260714-002",))
        except sqlite3.DatabaseError as exc:
            assert "FINANCE_TRANSACTION_DELETE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("referenced transaction delete should be blocked")


def test_finance_insert_for_pending_reconciliation_is_allowed(client):
    from app.database import get_connection

    response = client.post(
        "/api/finance/reconciliation/import",
        headers=finance_headers(client),
        json={
            "records": [
                {
                    "id": "R-PENDING-ALLOW",
                    "date": "2026-07-15",
                    "bank_flow_id": "BK-PENDING-ALLOW",
                    "system_flow_id": "F-PENDING-ALLOW",
                    "payer": "待匹配",
                    "amount": 1000,
                    "channel": "银行",
                }
            ]
        },
    )
    assert response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-PENDING-ALLOW", "P-1201", "2026-07-15", "租金收入", "A-1201", "林思远", 1000, "银行", "paid", "测试"),
        )
        transaction = db.execute("SELECT id FROM finance_transactions WHERE id = ?", ("F-PENDING-ALLOW",)).fetchone()

    assert transaction["id"] == "F-PENDING-ALLOW"


def test_direct_duplicate_pending_reconciliation_flow_is_allowed():
    from app.database import get_connection

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("R-DUP-PENDING", "2026-07-14", "BK-DUP-PENDING", "F-MISSING-002", "赵安琪", 19200, "支付宝", "pending", 0),
        )
        record = db.execute("SELECT id FROM reconciliation_records WHERE id = ?", ("R-DUP-PENDING",)).fetchone()

    assert record["id"] == "R-DUP-PENDING"


def test_finance_staff_can_confirm_pending_transaction(client):
    headers = finance_headers(client)
    create_response = client.post(
        "/api/finance/transactions",
        headers=headers,
        json={**TRANSACTION_PAYLOAD, "id": "F-CONFIRM-PENDING", "status": "pending"},
    )
    assert create_response.status_code == 200

    response = client.post("/api/finance/transactions/F-CONFIRM-PENDING/confirm", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "paid"


def test_finance_staff_can_confirm_overdue_transaction(client):
    headers = finance_headers(client)
    create_response = client.post(
        "/api/finance/transactions",
        headers=headers,
        json={**TRANSACTION_PAYLOAD, "id": "F-CONFIRM-OVERDUE", "status": "overdue"},
    )
    assert create_response.status_code == 200

    response = client.post("/api/finance/transactions/F-CONFIRM-OVERDUE/confirm", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "paid"


def test_cannot_confirm_paid_or_reconciled_transaction(client):
    headers = finance_headers(client)
    create_response = client.post(
        "/api/finance/transactions",
        headers=headers,
        json={**TRANSACTION_PAYLOAD, "id": "F-CONFIRM-PAID", "status": "paid"},
    )
    assert create_response.status_code == 200

    paid_response = client.post("/api/finance/transactions/F-CONFIRM-PAID/confirm", headers=headers)
    reconciled_response = client.post("/api/finance/transactions/F-20260714-001/confirm", headers=headers)

    assert paid_response.status_code == 409
    assert paid_response.json()["detail"]["code"] == "INVALID_FINANCE_STATUS"
    assert reconciled_response.status_code == 409
    assert reconciled_response.json()["detail"]["code"] == "INVALID_FINANCE_STATUS"


def test_viewer_cannot_confirm_transaction(client, viewer_token):
    response = client.post(
        "/api/finance/transactions/F-20260714-002/confirm",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


def test_confirm_missing_transaction_returns_not_found(client):
    response = client.post("/api/finance/transactions/missing/confirm", headers=finance_headers(client))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "FINANCE_TRANSACTION_NOT_FOUND"


def test_retry_pending_reconciliation_matches_after_transaction_exists(client):
    from app.database import get_connection

    headers = finance_headers(client)
    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-RETRY-MATCH",
                    "date": "2026-07-15",
                    "bank_flow_id": "BK-RETRY-MATCH",
                    "system_flow_id": "F-RETRY-MATCH",
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
            ("F-RETRY-MATCH", "P-1201", "2026-07-15", "租金收入", "A-1201", "林思远", 6800, "银行转账", "paid", "测试"),
        )

    response = client.post("/api/finance/reconciliation/R-RETRY-MATCH/retry-match", headers=headers)
    transactions_response = client.get("/api/finance/transactions", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    transaction = next(item for item in transactions_response.json()["items"] if item["id"] == "F-RETRY-MATCH")
    assert transaction["status"] == "reconciled"


def test_resolve_exception_reconciliation_marks_reviewed(client):
    headers = finance_headers(client)
    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-RESOLVE-EXCEPTION",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-RESOLVE-EXCEPTION",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19000,
                    "channel": "支付宝",
                },
            ]
        },
    )
    assert import_response.status_code == 200

    exception_response = client.post("/api/finance/reconciliation/R-RESOLVE-EXCEPTION/resolve", headers=headers)

    assert exception_response.status_code == 200
    assert exception_response.json()["status"] == "reviewed"


def test_cannot_resolve_pending_reconciliation(client):
    headers = finance_headers(client)
    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-RESOLVE-PENDING",
                    "date": "2026-07-15",
                    "bank_flow_id": "BK-RESOLVE-PENDING",
                    "system_flow_id": "missing",
                    "payer": "未知付款方",
                    "amount": 1000,
                    "channel": "银行",
                }
            ]
        },
    )
    assert import_response.status_code == 200

    response = client.post("/api/finance/reconciliation/R-RESOLVE-PENDING/resolve", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_RECONCILIATION_STATUS"


def test_cannot_resolve_or_retry_closed_reconciliation(client):
    headers = finance_headers(client)
    import_response = client.post(
        "/api/finance/reconciliation/import",
        headers=headers,
        json={
            "records": [
                {
                    "id": "R-CLOSED-REVIEWED",
                    "date": "2026-07-14",
                    "bank_flow_id": "BK-CLOSED-REVIEWED",
                    "system_flow_id": "F-20260714-002",
                    "payer": "赵安琪",
                    "amount": 19000,
                    "channel": "支付宝",
                }
            ]
        },
    )
    assert import_response.status_code == 200
    reviewed_response = client.post("/api/finance/reconciliation/R-CLOSED-REVIEWED/resolve", headers=headers)
    assert reviewed_response.status_code == 200

    matched_resolve_response = client.post("/api/finance/reconciliation/R-001/resolve", headers=headers)
    reviewed_resolve_response = client.post("/api/finance/reconciliation/R-CLOSED-REVIEWED/resolve", headers=headers)
    reviewed_retry_response = client.post("/api/finance/reconciliation/R-CLOSED-REVIEWED/retry-match", headers=headers)

    assert matched_resolve_response.status_code == 409
    assert matched_resolve_response.json()["detail"]["code"] == "INVALID_RECONCILIATION_STATUS"
    assert reviewed_resolve_response.status_code == 409
    assert reviewed_resolve_response.json()["detail"]["code"] == "INVALID_RECONCILIATION_STATUS"
    assert reviewed_retry_response.status_code == 409
    assert reviewed_retry_response.json()["detail"]["code"] == "INVALID_RECONCILIATION_STATUS"


def test_viewer_cannot_retry_or_resolve_reconciliation(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    retry_response = client.post("/api/finance/reconciliation/R-002/retry-match", headers=headers)
    resolve_response = client.post("/api/finance/reconciliation/R-002/resolve", headers=headers)

    assert retry_response.status_code == 403
    assert resolve_response.status_code == 403


def test_create_transaction_rejects_lifecycle_reserved_prefixes(client):
    headers = finance_headers(client)
    for prefix in ("SETTLE-MANUAL-001", "RENEWAL-MANUAL-001"):
        response = client.post(
            "/api/finance/transactions",
            headers=headers,
            json={**TRANSACTION_PAYLOAD, "id": prefix},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "RESERVED_FINANCE_TRANSACTION_ID"


def test_finance_staff_can_export_deposit_settlements_csv(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settle",
        headers=headers,
        json={"rent_deduction": 600, "settled_date": "2026-08-02"},
    )
    assert settlement_response.status_code == 200

    response = client.get("/api/finance/settlements/export", headers=finance_headers(client))

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "rent_deduction" in response.text
    assert "method" in response.text
    assert "note" in response.text
    assert settlement_response.json()["id"] in response.text
    with get_connection() as db:
        audit_row = db.execute(
            "SELECT 1 FROM audit_logs WHERE action = ? AND resource_type = ? AND resource_id = ?",
            ("export", "deposit_settlement", "all"),
        ).fetchone()
    assert audit_row is not None
