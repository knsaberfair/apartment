import sqlite3

from app import repositories
from app.database import get_connection, init_db
from app.security import hash_password


TENANT_PAYLOAD = {
    "id": "T-9901",
    "property_id": "P-1202",
    "name": "测试租客",
    "phone": "13800000000",
    "contract_id": "C-9901",
    "payment_status": "pending",
    "move_in_date": "2026-07-15",
    "lease_end": "2027-07-15",
    "balance": 5200,
}


def test_init_db_replaces_stale_tenant_integrity_trigger():
    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS tenants_contract_delete_guard")
        db.execute(
            """
            CREATE TRIGGER tenants_contract_delete_guard
            BEFORE DELETE ON tenants
            BEGIN
                SELECT RAISE(ABORT, 'STALE_TRIGGER');
            END
            """
        )
        db.commit()

    init_db()

    with get_connection() as db:
        trigger = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            ("tenants_contract_delete_guard",),
        ).fetchone()

    assert trigger is not None
    assert "STALE_TRIGGER" not in trigger["sql"]
    assert "room = OLD.room" in trigger["sql"]


def test_viewer_can_list_tenants(client, viewer_token):
    response = client.get("/api/tenants", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["items"]
    assert "property_id" in body["items"][0]


def test_viewer_can_list_tenant_property_options(client, viewer_token):
    response = client.get("/api/tenants/property-options", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body
    assert {"id", "building", "room", "status", "tenant", "lease_end", "tags"}.issubset(body[0])


def test_tenant_only_role_cannot_list_property_options(client):
    with get_connection() as db:
        db.execute("INSERT INTO roles (key, label, built_in) VALUES (?, ?, 0)", ("tenant_only", "租客只读"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("tenant_only", "tenants:view"))
        db.execute(
            """
            INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            ("tenant-only-user", "tenant_only", "租客只读", hash_password("tenant123"), "tenant_only", "2026-07-15T00:00:00+00:00"),
        )
        db.commit()

    token_response = client.post("/api/auth/login", json={"username": "tenant_only", "password": "tenant123"})
    assert token_response.status_code == 200

    response = client.get("/api/tenants/property-options", headers={"Authorization": f"Bearer {token_response.json()['access_token']}"})

    assert response.status_code == 403


def test_admin_can_create_tenant_and_sync_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "T-9901"
    assert body["property_id"] == "P-1202"
    assert body["room"] == "A-1202"

    properties_response = client.get("/api/properties", headers=headers)
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1202")
    assert property_item["tenant"] == "测试租客"
    assert property_item["lease_end"] == "2027-07-15"
    assert property_item["status"] == "occupied"


def test_admin_can_update_tenant_and_sync_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    property_response = client.post(
        "/api/properties",
        headers=headers,
        json={
            "id": "P-9902",
            "building": "D 栋",
            "room": "9902",
            "layout": "一室一厅",
            "area": 45,
            "rent": 4200,
            "status": "vacant",
            "tenant": None,
            "lease_end": None,
            "tags": [],
        },
    )
    assert property_response.status_code == 200

    response = client.put(
        "/api/tenants/T-9901",
        headers=headers,
        json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "property_id": "P-9902", "name": "更新租客", "lease_end": "2027-08-01", "balance": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "更新租客"
    assert body["property_id"] == "P-9902"
    assert body["room"] == "D-9902"

    properties_response = client.get("/api/properties", headers=headers)
    properties = {item["id"]: item for item in properties_response.json()["items"]}
    assert properties["P-1202"]["tenant"] is None
    assert properties["P-1202"]["status"] == "vacant"
    assert properties["P-9902"]["tenant"] == "更新租客"
    assert properties["P-9902"]["lease_end"] == "2027-08-01"
    assert properties["P-9902"]["status"] == "occupied"


def test_admin_can_delete_unreferenced_tenant_and_clear_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    response = client.delete("/api/tenants/T-9901", headers=headers)

    assert response.status_code == 204
    list_response = client.get("/api/tenants", headers=headers)
    assert "T-9901" not in {item["id"] for item in list_response.json()["items"]}

    properties_response = client.get("/api/properties", headers=headers)
    property_item = next(item for item in properties_response.json()["items"] if item["id"] == "P-1202")
    assert property_item["tenant"] is None
    assert property_item["lease_end"] is None
    assert property_item["status"] == "vacant"


def test_direct_property_tenant_desync_is_blocked_by_database_trigger(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET tenant = ? WHERE id = ?", ("陈旧租客", "P-1202"))
        except sqlite3.IntegrityError as exc:
            assert "PROPERTY_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("referenced property tenant desync should be blocked")


def test_update_tenant_clears_previous_property_with_stale_denormalized_tenant(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    property_response = client.post(
        "/api/properties",
        headers=headers,
        json={
            "id": "P-9902",
            "building": "D 栋",
            "room": "9902",
            "layout": "一室一厅",
            "area": 45,
            "rent": 4200,
            "status": "vacant",
            "tenant": None,
            "lease_end": None,
            "tags": [],
        },
    )
    assert property_response.status_code == 200
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET tenant = ? WHERE id = ?", ("陈旧租客", "P-1202"))
        except sqlite3.IntegrityError as exc:
            assert "PROPERTY_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("referenced property tenant desync should be blocked")

    response = client.put(
        "/api/tenants/T-9901",
        headers=headers,
        json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "property_id": "P-9902"},
    )

    assert response.status_code == 200
    properties_response = client.get("/api/properties", headers=headers)
    properties = {item["id"]: item for item in properties_response.json()["items"]}
    assert properties["P-1202"]["tenant"] is None
    assert properties["P-1202"]["status"] == "vacant"
    assert properties["P-9902"]["tenant"] == "测试租客"
    assert properties["P-9902"]["status"] == "occupied"


def test_viewer_cannot_mutate_tenants(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    update_response = client.put("/api/tenants/T-10001", headers=headers, json={key: value for key, value in TENANT_PAYLOAD.items() if key != "id"})
    delete_response = client.delete("/api/tenants/T-10001", headers=headers)

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_leasing_can_create_and_update_but_not_delete_tenants(client):
    token_response = client.post("/api/auth/login", json={"username": "leasing", "password": "leasing123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    update_response = client.put("/api/tenants/T-9901", headers=headers, json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "balance": 0})
    delete_response = client.delete("/api/tenants/T-9901", headers=headers)

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert delete_response.status_code == 403


def test_create_tenant_with_missing_property_returns_not_found(client, admin_token):
    response = client.post("/api/tenants", headers={"Authorization": f"Bearer {admin_token}"}, json={**TENANT_PAYLOAD, "property_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_create_duplicate_tenant_returns_conflict(client, admin_token):
    response = client.post("/api/tenants", headers={"Authorization": f"Bearer {admin_token}"}, json={**TENANT_PAYLOAD, "id": "T-10001"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_ALREADY_EXISTS"


def test_create_tenant_with_existing_contract_identity_returns_conflict(client, admin_token):
    response = client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**TENANT_PAYLOAD, "contract_id": "C-2026-0318"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_CONTRACTS"


def test_same_name_tenant_without_contract_overlap_can_be_created(client, admin_token):
    response = client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**TENANT_PAYLOAD, "name": "林思远"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "林思远"


def test_direct_duplicate_tenant_property_returns_conflict(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "id": "T-9902", "name": "重复租客", "contract_id": "C-9902"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ALREADY_OCCUPIED"


def test_direct_tenant_insert_update_delete_syncs_property():
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("T-DIRECT", "P-1202", "直接租客", "13800000000", "A-1202", "C-DIRECT", "pending", "2026-07-15", "2027-07-15", 0),
        )
        property_item = db.execute("SELECT status, tenant, lease_end FROM properties WHERE id = ?", ("P-1202",)).fetchone()
        assert property_item["status"] == "occupied"
        assert property_item["tenant"] == "直接租客"
        assert property_item["lease_end"] == "2027-07-15"

        db.execute("UPDATE tenants SET name = ?, lease_end = ? WHERE id = ?", ("直接租客更新", "2027-08-15", "T-DIRECT"))
        property_item = db.execute("SELECT status, tenant, lease_end FROM properties WHERE id = ?", ("P-1202",)).fetchone()
        assert property_item["status"] == "occupied"
        assert property_item["tenant"] == "直接租客更新"
        assert property_item["lease_end"] == "2027-08-15"

        db.execute("DELETE FROM tenants WHERE id = ?", ("T-DIRECT",))
        property_item = db.execute("SELECT status, tenant, lease_end FROM properties WHERE id = ?", ("P-1202",)).fetchone()
        assert property_item["status"] == "vacant"
        assert property_item["tenant"] is None
        assert property_item["lease_end"] is None


def test_direct_tenant_insert_with_mismatched_room_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("T-BAD-ROOM", "P-1202", "错误房间", "13800000000", "B-0806", "C-BAD-ROOM", "pending", "2026-07-15", "2027-07-15", 0),
            )
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("tenant room should match its property room key")


def test_direct_tenant_insert_for_unavailable_property_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("T-MAINTENANCE", "P-0806", "维修房源租客", "13800000000", "B-0806", "C-MAINTENANCE", "pending", "2026-07-15", "2027-07-15", 0),
            )
        except sqlite3.IntegrityError as exc:
            assert "PROPERTY_ALREADY_OCCUPIED" in str(exc)
        else:
            raise AssertionError("tenant insert for unavailable property should be blocked")


def test_tenant_repository_maps_database_occupancy_trigger_to_conflict(monkeypatch):
    monkeypatch.setattr(repositories, "_property_available_for_tenant", lambda *args: True)
    with get_connection() as db:
        try:
            repositories.create_tenant(db, {**TENANT_PAYLOAD, "id": "T-MAINTENANCE", "property_id": "P-0806", "contract_id": "C-MAINTENANCE"})
        except KeyError as exc:
            assert exc.args[0] == "PROPERTY_ALREADY_OCCUPIED"
        else:
            raise AssertionError("database occupancy trigger should map to domain conflict")


def test_direct_tenant_insert_for_matching_reserved_property_is_blocked_by_database_trigger():
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P-RESERVED", "D 栋", "9911", "D-9911", "一室一厅", 45, 4200, "reserved", "预订租客", "2027-07-01", "[]"),
        )
        try:
            db.execute(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("T-RESERVED", "P-RESERVED", "预订租客", "13800000000", "D-9911", "C-RESERVED", "pending", "2026-07-15", "2027-07-01", 0),
            )
        except sqlite3.IntegrityError as exc:
            assert "PROPERTY_ALREADY_OCCUPIED" in str(exc)
        else:
            raise AssertionError("tenant insert for reserved property should be blocked even when tenant metadata matches")


def test_direct_tenant_insert_with_invalid_payload_is_blocked_by_database_trigger():
    with get_connection() as db:
        for tenant_id, payment_status, balance, move_in_date, lease_end in (
            ("T-BAD-STATUS", "invalid", 0, "2026-07-15", "2027-07-15"),
            ("T-BAD-BALANCE", "pending", -1, "2026-07-15", "2027-07-15"),
            ("T-BAD-DATE", "pending", 0, "2027-07-15", "2026-07-15"),
            ("T-BAD-CALENDAR-DATE", "pending", 0, "2026-02-30", "2027-07-15"),
        ):
            try:
                db.execute(
                    """
                    INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tenant_id, "P-1202", "错误租客", "13800000000", "A-1202", f"C-{tenant_id}", payment_status, move_in_date, lease_end, balance),
                )
            except sqlite3.IntegrityError as exc:
                assert "INVALID_TENANT_PAYLOAD" in str(exc)
            else:
                raise AssertionError("invalid tenant payload should be blocked")


def test_direct_duplicate_tenant_contract_id_is_blocked_by_database_index(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P-9902", "D 栋", "9902", "D-9902", "一室一厅", 45, 4200, "vacant", None, None, "[]"),
        )
        try:
            db.execute(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("T-DUP-CONTRACT", "P-9902", "重复合同", "13800000000", "D-9902", "C-9901", "pending", "2026-07-15", "2027-07-15", 0),
            )
        except sqlite3.IntegrityError as exc:
            assert "tenants.contract_id" in str(exc) or "idx_tenants_contract_id" in str(exc)
        else:
            raise AssertionError("duplicate tenant contract id should be blocked")


def test_cannot_delete_tenant_referenced_by_contract(client, admin_token):
    response = client.delete("/api/tenants/T-10001", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_CONTRACTS"


def test_cannot_delete_tenant_referenced_by_contract_id(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C-9901", "P-1202", "测试租客", "A-1202", "2026-07-15", "2027-07-15", 5200, 5200, "pending", 365),
        )
        db.execute("UPDATE contracts SET status = ? WHERE id = ?", ("active", "C-9901"))
        db.commit()

    response = client.delete("/api/tenants/T-9901", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_CONTRACTS"


def test_direct_contract_with_mismatched_room_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-STALE-ROOM", "P-0806", "其他租客", "A-1202", "2026-07-15", "2027-07-15", 5200, 5200, "active", 365),
            )
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("contract room should match its property room key")


def test_direct_contract_with_mismatched_property_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-STALE-PROPERTY", "P-1202", "其他租客", "STALE-ROOM", "2026-07-15", "2027-07-15", 5200, 5200, "active", 365),
            )
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("contract property should match its room key")


def test_direct_maintenance_order_with_mismatched_room_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("M-BAD-ROOM", "P-1202", "水管维修", "B-0806", "租客", "plumbing", "medium", "open", "未分配", "2026-07-15", "2026-07-20"),
            )
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("maintenance order room should match its property room key")


def test_direct_finance_transaction_with_mismatched_room_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("F-BAD-ROOM", "P-1202", "2026-07-15", "rent", "B-0806", "租客", 5200, "bank", "paid", "租金"),
            )
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("finance transaction room should match its property room key")


def test_cannot_delete_tenant_referenced_by_maintenance_order(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("M-9901", "P-1202", "水管维修", "A-1202", "其他租客", "plumbing", "medium", "open", "未分配", "2026-07-15", "2026-07-20"),
        )
        db.commit()

    response = client.delete("/api/tenants/T-9901", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_RECORDS"


def test_cannot_delete_tenant_referenced_by_finance_transaction(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-9901", "P-1202", "2026-07-15", "rent", "A-1202", "其他租客", 5200, "bank", "paid", "租金"),
        )
        db.commit()

    response = client.delete("/api/tenants/T-9901", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_RECORDS"


def test_cannot_update_tenant_referenced_by_maintenance_order(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("M-9901", "P-1202", "水管维修", "A-1202", "其他租客", "plumbing", "medium", "open", "未分配", "2026-07-15", "2026-07-20"),
        )
        db.commit()

    response = client.put(
        "/api/tenants/T-9901",
        headers=headers,
        json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "name": "更新租客"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_RECORDS"


def test_cannot_update_tenant_referenced_by_finance_transaction(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-9901", "P-1202", "2026-07-15", "rent", "A-1202", "其他租客", 5200, "bank", "paid", "租金"),
        )
        db.commit()

    response = client.put(
        "/api/tenants/T-9901",
        headers=headers,
        json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "property_id": "P-1203"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_RELATED_RECORDS"


def test_direct_tenant_delete_with_related_activity_is_blocked_by_database_trigger(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("M-9901", "P-1202", "水管维修", "A-1202", "其他租客", "plumbing", "medium", "open", "未分配", "2026-07-15", "2026-07-20"),
        )
        try:
            db.execute("DELETE FROM tenants WHERE id = ?", ("T-9901",))
        except sqlite3.IntegrityError as exc:
            assert "TENANT_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("tenant delete should be blocked by database trigger")


def test_direct_tenant_room_update_is_blocked_by_database_trigger(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        try:
            db.execute("UPDATE tenants SET room = ? WHERE id = ?", ("X-0001", "T-9901"))
        except sqlite3.IntegrityError as exc:
            assert "RELATED_PROPERTY_REQUIRED" in str(exc)
        else:
            raise AssertionError("tenant room update should be blocked by database trigger")


def test_direct_tenant_identity_update_with_related_activity_is_blocked_by_database_trigger(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-9901", "P-1202", "2026-07-15", "rent", "A-1202", "其他租客", 5200, "bank", "paid", "租金"),
        )
        try:
            db.execute("UPDATE tenants SET name = ? WHERE id = ?", ("更新租客", "T-9901"))
        except sqlite3.IntegrityError as exc:
            assert "TENANT_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("tenant identity update should be blocked by database trigger")


def test_direct_contract_conflicting_with_existing_tenant_is_blocked_by_database_trigger(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-OTHER", "P-1202", "其他租客", "A-1202", "2026-07-15", "2027-07-15", 5200, 5200, "active", 365),
            )
        except sqlite3.IntegrityError as exc:
            assert "TENANT_HAS_CONTRACTS" in str(exc) or "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY" in str(exc)
        else:
            raise AssertionError("contract conflicting with existing tenant should be blocked")


def test_direct_duplicate_contract_property_is_blocked_by_database_trigger():
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P-9912", "D 栋", "9912", "D-9912", "一室一厅", 45, 4200, "vacant", None, None, "[]"),
        )
        db.execute(
            """
            INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C-9912-A", "P-9912", "合同租客A", "D-9912", "2026-07-15", "2027-07-15", 4200, 4200, "pending", 365),
        )
        try:
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("C-9912-B", "P-9912", "合同租客B", "D-9912", "2026-08-01", "2027-08-01", 4200, 4200, "pending", 365),
            )
        except sqlite3.IntegrityError as exc:
            assert "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY" in str(exc)
        else:
            raise AssertionError("duplicate contract property should be blocked")


def test_create_tenant_for_non_vacant_property_returns_conflict(client, admin_token):
    response = client.post("/api/tenants", headers={"Authorization": f"Bearer {admin_token}"}, json={**TENANT_PAYLOAD, "property_id": "P-0806"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ALREADY_OCCUPIED"


def test_update_tenant_to_property_used_by_another_tenant_returns_conflict(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    response = client.put("/api/tenants/T-9901", headers=headers, json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "property_id": "P-1201"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ALREADY_OCCUPIED"


def test_update_tenant_with_missing_property_returns_not_found(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/tenants", headers=headers, json=TENANT_PAYLOAD)
    assert create_response.status_code == 200

    response = client.put("/api/tenants/T-9901", headers=headers, json={**{key: value for key, value in TENANT_PAYLOAD.items() if key != "id"}, "property_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_update_missing_tenant_returns_not_found(client, admin_token):
    response = client.put("/api/tenants/missing", headers={"Authorization": f"Bearer {admin_token}"}, json={key: value for key, value in TENANT_PAYLOAD.items() if key != "id"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "TENANT_NOT_FOUND"


def test_cannot_update_contract_protected_tenant_identity_fields(client, admin_token):
    response = client.put(
        "/api/tenants/T-10001",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "property_id": "P-1201",
            "name": "林思远更新",
            "phone": "138****0921",
            "contract_id": "C-2026-0318",
            "payment_status": "paid",
            "move_in_date": "2026-03-18",
            "lease_end": "2027-03-18",
            "balance": 0,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TENANT_HAS_CONTRACTS"


def test_tenant_validation_errors(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    blank_response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "name": "  "})
    status_response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "payment_status": "invalid"})
    balance_response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "balance": -1})
    invalid_date_response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "move_in_date": "2026-13-01"})
    reversed_date_response = client.post("/api/tenants", headers=headers, json={**TENANT_PAYLOAD, "move_in_date": "2027-07-15", "lease_end": "2026-07-15"})

    assert blank_response.status_code == 422
    assert status_response.status_code == 422
    assert balance_response.status_code == 422
    assert invalid_date_response.status_code == 422
    assert reversed_date_response.status_code == 422


def test_moved_out_tenant_does_not_block_new_tenant_for_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    move_out_response = client.post(
        "/api/contracts/C-2026-0318/move-out",
        headers=headers,
        json={"move_out_date": "2026-08-01", "reason": "正常退租"},
    )
    assert move_out_response.status_code == 200

    response = client.post(
        "/api/tenants",
        headers=headers,
        json={**TENANT_PAYLOAD, "id": "T-AFTER-MOVEOUT", "property_id": "P-1201", "contract_id": "C-AFTER-MOVEOUT", "name": "新租客"},
    )

    assert response.status_code == 200
    assert response.json()["property_id"] == "P-1201"
