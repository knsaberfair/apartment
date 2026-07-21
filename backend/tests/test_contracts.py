import sqlite3

from app.database import get_connection
from app.security import hash_password


CONTRACT_PAYLOAD = {
    "id": "C-9901",
    "property_id": "P-1202",
    "tenant": "测试租客",
    "start_date": "2026-07-15",
    "end_date": "2027-07-15",
    "monthly_rent": 5200,
    "deposit": 10400,
}


def test_viewer_can_list_contracts(client, viewer_token):
    response = client.get("/api/contracts", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["items"]


def test_contract_property_options_require_contract_create(client, viewer_token, admin_token):
    viewer_response = client.get("/api/contracts/property-options", headers={"Authorization": f"Bearer {viewer_token}"})
    admin_response = client.get("/api/contracts/property-options", headers={"Authorization": f"Bearer {admin_token}"})

    assert viewer_response.status_code == 403
    assert admin_response.status_code == 200
    assert admin_response.json()


def test_admin_can_create_update_approve_and_terminate_contract(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["status"] == "pending"
    assert body["room"] == "A-1202"

    update_response = client.put(
        "/api/contracts/C-9901",
        headers=headers,
        json={**{key: value for key, value in CONTRACT_PAYLOAD.items() if key != "id"}, "tenant": "更新租客", "monthly_rent": 5600},
    )
    assert update_response.status_code == 200
    assert update_response.json()["tenant"] == "更新租客"
    assert update_response.json()["monthly_rent"] == 5600

    approve_response = client.post("/api/contracts/C-9901/approve", headers=headers)
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"

    properties_response = client.get("/api/properties", headers=headers)
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1202")
    assert property_item["status"] == "occupied"
    assert property_item["tenant"] == "更新租客"
    assert property_item["lease_end"] == "2027-07-15"

    terminate_response = client.post("/api/contracts/C-9901/terminate", headers=headers)
    assert terminate_response.status_code == 200
    assert terminate_response.json()["status"] == "terminated"

    properties_response = client.get("/api/properties", headers=headers)
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1202")
    assert property_item["status"] == "vacant"
    assert property_item["tenant"] is None
    assert property_item["lease_end"] is None


def test_viewer_cannot_mutate_contracts(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    update_response = client.put("/api/contracts/C-2026-0701", headers=headers, json={key: value for key, value in CONTRACT_PAYLOAD.items() if key != "id"})
    approve_response = client.post("/api/contracts/C-2026-0701/approve", headers=headers)
    terminate_response = client.post("/api/contracts/C-2026-0701/terminate", headers=headers)

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert approve_response.status_code == 403
    assert terminate_response.status_code == 403


def test_leasing_can_create_but_not_approve_or_terminate_contracts(client):
    token_response = client.post("/api/auth/login", json={"username": "leasing", "password": "leasing123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    approve_response = client.post("/api/contracts/C-9901/approve", headers=headers)
    terminate_response = client.post("/api/contracts/C-9901/terminate", headers=headers)

    assert create_response.status_code == 200
    assert approve_response.status_code == 403
    assert terminate_response.status_code == 403


def test_create_contract_for_missing_property_returns_not_found(client, admin_token):
    response = client.post("/api/contracts", headers={"Authorization": f"Bearer {admin_token}"}, json={**CONTRACT_PAYLOAD, "property_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_create_duplicate_property_contract_returns_conflict(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    assert create_response.status_code == 200

    response = client.post("/api/contracts", headers=headers, json={**CONTRACT_PAYLOAD, "id": "C-9902"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY"


def test_cannot_approve_or_update_non_pending_contract(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    assert create_response.status_code == 200
    approve_response = client.post("/api/contracts/C-9901/approve", headers=headers)
    assert approve_response.status_code == 200

    update_response = client.put("/api/contracts/C-9901", headers=headers, json={key: value for key, value in CONTRACT_PAYLOAD.items() if key != "id"})
    second_approve_response = client.post("/api/contracts/C-9901/approve", headers=headers)

    assert update_response.status_code == 409
    assert update_response.json()["detail"]["code"] == "INVALID_CONTRACT_STATUS"
    assert second_approve_response.status_code == 409
    assert second_approve_response.json()["detail"]["code"] == "INVALID_CONTRACT_STATUS"


def test_cannot_terminate_already_terminated_contract(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/contracts", headers=headers, json=CONTRACT_PAYLOAD)
    assert create_response.status_code == 200
    terminate_response = client.post("/api/contracts/C-9901/terminate", headers=headers)
    assert terminate_response.status_code == 200

    second_terminate_response = client.post("/api/contracts/C-9901/terminate", headers=headers)

    assert second_terminate_response.status_code == 409
    assert second_terminate_response.json()["detail"]["code"] == "INVALID_CONTRACT_STATUS"


def test_admin_can_approve_seeded_pending_contract_with_tenant(client, admin_token):
    response = client.post("/api/contracts/C-2026-0701/approve", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "active"

    properties_response = client.get("/api/properties", headers={"Authorization": f"Bearer {admin_token}"})
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1608")
    assert property_item["status"] == "occupied"
    assert property_item["tenant"] == "赵安琪"
    assert property_item["lease_end"] == "2027-07-01"


def test_cannot_terminate_contract_with_active_tenant_record(client, admin_token):
    response = client.post("/api/contracts/C-2026-0318/terminate", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_CONTRACTS"


def test_direct_contract_termination_with_tenant_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("UPDATE contracts SET status = ?, days_left = 0 WHERE id = ?", ("terminated", "C-2026-0318"))
        except sqlite3.DatabaseError as exc:
            assert "TENANT_HAS_RELATED_CONTRACTS" in str(exc)
        else:
            raise AssertionError("contract termination with active tenant should be blocked")


def test_direct_invalid_contract_payload_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-BAD-DATE", "P-1202", "坏日期租客", "A-1202", "2026-02-30", "2027-07-15", 5200, 10400, "pending", 365),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_CONTRACT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid contract date should be blocked")


def test_direct_active_contract_insert_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-DIRECT-ACTIVE", "P-1202", "直写租客", "A-1202", "2026-07-15", "2027-07-15", 5200, 10400, "active", 365),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_CONTRACT_STATUS" in str(exc)
        else:
            raise AssertionError("active contract insert should be blocked")


def test_direct_invalid_contract_status_transition_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("UPDATE contracts SET status = ? WHERE id = ?", ("pending", "C-2026-0318"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_CONTRACT_STATUS" in str(exc)
        else:
            raise AssertionError("invalid contract status transition should be blocked")


def test_direct_non_pending_contract_business_update_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("UPDATE contracts SET monthly_rent = ? WHERE id = ?", (1, "C-2026-0318"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_CONTRACT_STATUS" in str(exc)
        else:
            raise AssertionError("non-pending contract business update should be blocked")


def test_direct_contract_delete_is_blocked_by_database_trigger():
    from app.database import get_connection

    with get_connection() as db:
        try:
            db.execute("DELETE FROM contracts WHERE id = ?", ("C-2026-0318",))
        except sqlite3.DatabaseError as exc:
            assert "CONTRACT_DELETE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("contract delete should be blocked")


def test_admin_can_renew_contract_and_generate_updated_rent_bill(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.post(
        "/api/contracts/C-2026-0318/renew",
        headers=headers,
        json={"new_end_date": "2027-09-18", "monthly_rent": 7000, "deposit": 14000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract_id"] == "C-2026-0318"
    assert body["old_end_date"] == "2027-03-18"
    assert body["new_end_date"] == "2027-09-18"
    with get_connection() as db:
        transaction = db.execute("SELECT * FROM finance_transactions WHERE id = ?", (body["id"],)).fetchone()
    assert transaction is not None
    assert transaction["type"] == "续签押金调整"
    assert transaction["amount"] == 400
    assert transaction["status"] == "pending"
    assert transaction["lifecycle_type"] == "renewal"
    contracts_response = client.get("/api/contracts", headers=headers)
    renewed = next(item for item in contracts_response.json()["items"] if item["id"] == "C-2026-0318")
    assert renewed["end_date"] == "2027-09-18"
    assert renewed["monthly_rent"] == 7000


def test_admin_can_move_out_and_settle_deposit(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out = move_out_response.json()
    assert move_out["status"] == "pending_settlement"

    tenants_response = client.get("/api/tenants", headers=headers)
    tenant = next(item for item in tenants_response.json()["items"] if item["id"] == "T-10001")
    assert tenant["status"] == "moved_out"
    assert tenant["move_out_date"] == "2026-08-01"

    properties_response = client.get("/api/properties", headers=headers)
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1201")
    assert property_item["status"] == "vacant"
    assert property_item["tenant"] is None

    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out['id']}/settle",
        headers=headers,
        json={"deductions": 600, "settled_date": "2026-08-02", "method": "现金", "note": "=退租备注"},
    )
    assert settlement_response.status_code == 200
    settlement = settlement_response.json()
    assert settlement["refund_amount"] == 13000
    assert settlement["finance_transaction_id"] == settlement["id"]
    assert settlement["method"] == "现金"
    assert settlement["note"] == "=退租备注"
    with get_connection() as db:
        transaction = db.execute("SELECT method, note FROM finance_transactions WHERE id = ?", (settlement["finance_transaction_id"],)).fetchone()
    assert transaction["method"] == "现金"
    assert transaction["note"] == "=退租备注"


def test_viewer_cannot_read_deposit_settlement_details(client, admin_token, viewer_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=admin_headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settle",
        headers=admin_headers,
        json={"deductions": 600, "settled_date": "2026-08-02"},
    )
    assert settlement_response.status_code == 200

    response = client.get(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settlements",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


def test_settlement_rejects_date_before_move_out(client, admin_token):
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
        json={"deductions": 0, "settled_date": "2026-07-31"},
    )

    assert settlement_response.status_code == 422
    assert settlement_response.json()["detail"]["code"] == "INVALID_SETTLEMENT_PAYLOAD"


def test_zero_refund_settlement_has_no_finance_transaction(client, admin_token):
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
        json={"deductions": 13600, "settled_date": "2026-08-02"},
    )

    assert settlement_response.status_code == 200
    settlement = settlement_response.json()
    assert settlement["refund_amount"] == 0
    assert settlement["finance_transaction_id"] is None


def test_lifecycle_records_are_database_protected(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    renewal_response = client.post(
        "/api/contracts/C-2026-0318/renew",
        headers=headers,
        json={"new_end_date": "2027-09-18", "monthly_rent": 7000, "deposit": 14000},
    )
    assert renewal_response.status_code == 200
    move_out_response = client.post(
        "/api/contracts/C-2025-0822/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settle",
        headers=headers,
        json={"deductions": 0, "settled_date": "2026-08-02"},
    )
    assert settlement_response.status_code == 200

    with get_connection() as db:
        for table, row_id in (
            ("contract_renewals", renewal_response.json()["id"]),
            ("move_outs", move_out_response.json()["id"]),
            ("deposit_settlements", settlement_response.json()["id"]),
        ):
            try:
                db.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            except Exception as exc:
                assert "LIFECYCLE_RECORD_DELETE_FORBIDDEN" in str(exc)
            else:
                raise AssertionError(f"{table} delete should be blocked")

        try:
            db.execute("UPDATE move_outs SET reason = ? WHERE id = ?", ("tamper", move_out_response.json()["id"]))
        except Exception as exc:
            assert "LIFECYCLE_RECORD_UPDATE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("move_out arbitrary update should be blocked")

        finance_transaction_id = settlement_response.json()["finance_transaction_id"]
        assert finance_transaction_id is not None
        try:
            db.execute("UPDATE finance_transactions SET amount = amount - 1 WHERE id = ?", (finance_transaction_id,))
        except Exception as exc:
            assert "INVALID_FINANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("settlement finance transaction update should be blocked")

        try:
            db.execute("DELETE FROM finance_transactions WHERE id = ?", (finance_transaction_id,))
        except Exception as exc:
            assert "FINANCE_TRANSACTION_DELETE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("settlement finance transaction delete should be blocked")


def test_database_rejects_duplicate_move_out_and_settlement(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out = move_out_response.json()

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO move_outs (id, contract_id, property_id, tenant, room, move_out_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("MOVEOUT-DUP", move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], "2026-08-02", "duplicate", "pending_settlement", "2026-08-02"),
            )
        except Exception as exc:
            assert "UNIQUE constraint failed" in str(exc) or "INVALID_MOVE_OUT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("duplicate move_out should be blocked")

    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out['id']}/settle",
        headers=headers,
        json={"deductions": 600, "settled_date": "2026-08-02"},
    )
    assert settlement_response.status_code == 200
    settlement = settlement_response.json()

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, refund_amount, settled_date, status, finance_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-DUP", settlement["move_out_id"], settlement["contract_id"], settlement["property_id"], settlement["tenant"], settlement["room"], settlement["deposit"], settlement["deductions"], settlement["refund_amount"], "2026-08-03", "settled", "SETTLE-DUP"),
            )
        except Exception as exc:
            assert "UNIQUE constraint failed" in str(exc) or "INVALID_SETTLEMENT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("duplicate settlement should be blocked")


def test_database_rejects_invalid_lifecycle_direct_inserts(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out = move_out_response.json()

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contract_renewals (id, contract_id, property_id, tenant, room, old_end_date, new_end_date, monthly_rent, deposit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("RENEWAL-TERMINATED", move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], "2027-03-18", "2027-09-18", 7000, 14000, "2026-08-01"),
            )
        except Exception as exc:
            assert "INVALID_CONTRACT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("renewal for terminated contract should be blocked")

        try:
            db.execute(
                """
                INSERT INTO move_outs (id, contract_id, property_id, tenant, room, move_out_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("MOVEOUT-PENDING", "C-PENDING-0710", "P-0902", "梁佳佳", "A-0902", "2026-08-01", "invalid", "pending_settlement", "2026-08-01"),
            )
        except Exception as exc:
            assert "INVALID_MOVE_OUT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("move-out for pending contract should be blocked")

        try:
            db.execute(
                """
                INSERT INTO move_outs (id, contract_id, property_id, tenant, room, move_out_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("MOVEOUT-BAD-DATE", "C-2025-0822", "P-0808", "陈晓", "A-0808", "2026-02-30", "invalid", "pending_settlement", "2026-08-01"),
            )
        except Exception as exc:
            assert "INVALID_MOVE_OUT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid move-out calendar date should be blocked")

        try:
            db.execute(
                """
                INSERT INTO contract_renewals (id, contract_id, property_id, tenant, room, old_end_date, new_end_date, monthly_rent, deposit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("RENEWAL-BAD-DATE", "C-2026-0318", "P-1201", "林思远", "A-1201", "2027-03-18", "2027-02-30", 7000, 14000, "2026-08-01"),
            )
        except Exception as exc:
            assert "INVALID_CONTRACT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid renewal calendar date should be blocked")

        try:
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, refund_amount, settled_date, status, finance_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-NEGATIVE", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], 1000, 1200, -200, "2026-08-02", "settled", None),
            )
        except Exception as exc:
            assert "INVALID_SETTLEMENT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("negative settlement refund should be blocked")

        try:
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, refund_amount, settled_date, status, finance_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-BAD-DATE", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], 1000, 0, 1000, "2026-02-30", "settled", None),
            )
        except Exception as exc:
            assert "INVALID_SETTLEMENT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid settlement calendar date should be blocked")

        try:
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, refund_amount, settled_date, status, finance_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-MISMATCH", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], 1000, 100, 900, "2026-08-02", "settled", "SETTLE-MISMATCH"),
            )
        except Exception as exc:
            assert "INVALID_SETTLEMENT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("settlement details must equal total deductions")

        try:
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, refund_amount, settled_date, status, finance_transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-WRONG-DEPOSIT", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], 1, 0, 0, "2026-08-02", "settled", None),
            )
        except Exception as exc:
            assert "INVALID_SETTLEMENT_PAYLOAD" in str(exc)
        else:
            raise AssertionError("settlement deposit must match contract deposit")

        contract_deposit = db.execute("SELECT deposit FROM contracts WHERE id = ?", (move_out["contract_id"],)).fetchone()["deposit"]
        try:
            db.execute(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("SETTLE-ORPHAN", move_out["property_id"], "2026-08-02", "押金退还", move_out["room"], move_out["tenant"], -contract_deposit, "银行转账", "paid", "invalid", move_out["contract_id"], "SETTLE-ORPHAN", "settlement"),
            )
        except Exception as exc:
            assert "INVALID_FINANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("orphan settlement finance transaction should be blocked")


def test_direct_settlement_insert_marks_move_out_settled(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out = move_out_response.json()

    with get_connection() as db:
        contract_deposit = db.execute("SELECT deposit FROM contracts WHERE id = ?", (move_out["contract_id"],)).fetchone()["deposit"]
        db.execute(
            """
            INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, other_deduction, refund_amount, settled_date, status, finance_transaction_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("SETTLE-DIRECT-ZERO", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], contract_deposit, contract_deposit, contract_deposit, 0, "2026-08-02", "settled", None),
        )
        status = db.execute("SELECT status FROM move_outs WHERE id = ?", (move_out["id"],)).fetchone()["status"]

    assert status == "settled"


def test_direct_positive_refund_settlement_creates_finance_transaction(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200
    move_out = move_out_response.json()

    with get_connection() as db:
        contract_deposit = db.execute("SELECT deposit FROM contracts WHERE id = ?", (move_out["contract_id"],)).fetchone()["deposit"]
        db.execute(
            """
            INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, other_deduction, refund_amount, settled_date, status, finance_transaction_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("SETTLE-DIRECT-POSITIVE", move_out["id"], move_out["contract_id"], move_out["property_id"], move_out["tenant"], move_out["room"], contract_deposit, 600, 600, contract_deposit - 600, "2026-08-02", "settled", "SETTLE-DIRECT-POSITIVE"),
        )
        transaction = db.execute("SELECT * FROM finance_transactions WHERE id = ?", ("SETTLE-DIRECT-POSITIVE",)).fetchone()

    assert transaction is not None
    assert transaction["settlement_id"] == "SETTLE-DIRECT-POSITIVE"
    assert transaction["amount"] == -(contract_deposit - 600)
    assert transaction["method"] == "银行转账"
    assert transaction["note"] == "退租押金结算"
    assert transaction["lifecycle_type"] == "settlement"


def test_settle_requires_finance_confirm_permission(client):
    with get_connection() as db:
        db.execute("INSERT INTO roles (key, label, built_in) VALUES (?, ?, 0)", ("terminator", "终止专员"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("terminator", "contracts:terminate"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("terminator", "contracts:view"))
        db.execute(
            """
            INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            ("U-TERMINATOR", "terminator", "终止专员", hash_password("terminator123"), "terminator", "2026-07-01"),
        )
        db.commit()

    login_response = client.post("/api/auth/login", json={"username": "terminator", "password": "terminator123"})
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200

    settlement_response = client.post(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settle",
        headers=headers,
        json={"deductions": 600, "settled_date": "2026-08-02"},
    )

    assert settlement_response.status_code == 403


def test_viewer_cannot_mutate_contract_lifecycle(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    renew_response = client.post(
        "/api/contracts/C-2026-0318/renew",
        headers=headers,
        json={"new_end_date": "2027-09-18", "monthly_rent": 7000, "deposit": 14000},
    )
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )

    assert renew_response.status_code == 403
    assert move_out_response.status_code == 403


def test_settlement_accepts_detailed_deductions_and_legacy_total(client, admin_token):
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
        json={"rent_deduction": 300, "utility_deduction": 200, "damage_deduction": 100, "settled_date": "2026-08-02"},
    )

    assert settlement_response.status_code == 200
    settlement = settlement_response.json()
    assert settlement["deductions"] == 600
    assert settlement["rent_deduction"] == 300
    assert settlement["utility_deduction"] == 200
    assert settlement["damage_deduction"] == 100
    assert settlement["refund_amount"] == 13000


def test_settlement_rejects_mismatched_deduction_total(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200

    response = client.post(
        f"/api/contracts/move-outs/{move_out_response.json()['id']}/settle",
        headers=headers,
        json={"deductions": 600, "rent_deduction": 300, "settled_date": "2026-08-02"},
    )

    assert response.status_code == 422
