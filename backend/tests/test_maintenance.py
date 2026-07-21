import sqlite3

from app.database import get_connection


MAINTENANCE_PAYLOAD = {
    "id": "M-9901",
    "property_id": "P-1202",
    "title": "水龙头漏水",
    "tenant": "测试租客",
    "category": "水电",
    "priority": "medium",
    "due_at": "2027-12-31",
}


def test_viewer_can_list_maintenance_orders(client, viewer_token):
    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["items"]


def test_maintenance_property_options_require_create_permission(client, viewer_token):
    viewer_response = client.get("/api/maintenance-orders/property-options", headers={"Authorization": f"Bearer {viewer_token}"})
    token_response = client.post("/api/auth/login", json={"username": "maintenance", "password": "maintenance123"})
    assert token_response.status_code == 200
    maintenance_response = client.get(
        "/api/maintenance-orders/property-options",
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
    )

    assert viewer_response.status_code == 403
    assert maintenance_response.status_code == 200
    assert maintenance_response.json()
    assert set(maintenance_response.json()[0]) == {"id", "building", "room"}


def test_maintenance_staff_can_create_assign_and_resolve_order(client):
    token_response = client.post("/api/auth/login", json={"username": "maintenance", "password": "maintenance123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    create_response = client.post("/api/maintenance-orders", headers=headers, json=MAINTENANCE_PAYLOAD)
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["status"] == "open"
    assert body["assignee"] == "未分配"
    assert body["room"] == "A-1202"

    assign_response = client.post("/api/maintenance-orders/M-9901/assign", headers=headers, json={"assignee": "维修组-王工"})
    assert assign_response.status_code == 200
    assert assign_response.json()["status"] == "in_progress"
    assert assign_response.json()["assignee"] == "维修组-王工"

    resolve_response = client.post("/api/maintenance-orders/M-9901/resolve", headers=headers)
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"


def test_viewer_cannot_mutate_maintenance_orders(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    create_response = client.post("/api/maintenance-orders", headers=headers, json=MAINTENANCE_PAYLOAD)
    assign_response = client.post("/api/maintenance-orders/M-240713-08/assign", headers=headers, json={"assignee": "维修组-王工"})
    resolve_response = client.post("/api/maintenance-orders/M-240713-08/resolve", headers=headers)

    assert create_response.status_code == 403
    assert assign_response.status_code == 403
    assert resolve_response.status_code == 403


def test_create_maintenance_order_for_missing_property_returns_not_found(client, admin_token):
    response = client.post(
        "/api/maintenance-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**MAINTENANCE_PAYLOAD, "property_id": "missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_cannot_resolve_open_order(client):
    token_response = client.post("/api/auth/login", json={"username": "maintenance", "password": "maintenance123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    response = client.post("/api/maintenance-orders/M-240713-08/resolve", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_MAINTENANCE_STATUS"



def test_cannot_assign_or_resolve_already_resolved_order(client):
    token_response = client.post("/api/auth/login", json={"username": "maintenance", "password": "maintenance123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    resolve_response = client.post("/api/maintenance-orders/M-240711-11/resolve", headers=headers)
    assign_response = client.post("/api/maintenance-orders/M-240711-11/assign", headers=headers, json={"assignee": "维修组-王工"})

    assert resolve_response.status_code == 409
    assert resolve_response.json()["detail"]["code"] == "INVALID_MAINTENANCE_STATUS"
    assert assign_response.status_code == 409
    assert assign_response.json()["detail"]["code"] == "INVALID_MAINTENANCE_STATUS"


def test_direct_non_open_maintenance_insert_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("M-DIRECT", "P-1202", "直写工单", "A-1202", "测试租客", "水电", "medium", "resolved", "维修组", "2026-07-15", "2026-07-16"),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("non-open maintenance insert should be blocked")


def test_direct_invalid_maintenance_status_transition_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("resolved", "M-240713-08"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("invalid maintenance status transition should be blocked")



def test_direct_open_to_in_progress_without_assignee_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("in_progress", "M-240713-08"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("unassigned in-progress transition should be blocked")



def test_direct_maintenance_id_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET id = ? WHERE id = ?", ("M-RENAMED", "M-240713-08"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("maintenance id update should be blocked")


def test_direct_resolved_maintenance_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET assignee = ? WHERE id = ?", ("维修组-王工", "M-240711-11"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("resolved maintenance update should be blocked")



def test_direct_open_maintenance_detail_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET title = ? WHERE id = ?", ("直接改标题", "M-240713-08"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("open maintenance detail update should be blocked")



def test_direct_in_progress_maintenance_detail_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET title = ? WHERE id = ?", ("直接改标题", "M-240714-01"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("in-progress maintenance detail update should be blocked")



def test_direct_open_maintenance_assignee_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE maintenance_orders SET assignee = ? WHERE id = ?", ("维修组-王工", "M-240713-08"))
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_STATUS" in str(exc)
        else:
            raise AssertionError("open maintenance assignee update should be blocked")



def test_direct_maintenance_delete_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("DELETE FROM maintenance_orders WHERE id = ?", ("M-240713-08",))
        except sqlite3.DatabaseError as exc:
            assert "MAINTENANCE_ORDER_DELETE_FORBIDDEN" in str(exc)
        else:
            raise AssertionError("maintenance delete should be blocked")



def test_legacy_relative_maintenance_due_date_is_normalized_on_init(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("今日 18:00", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["due_at"] == order["created_at"]



def test_unrecognized_legacy_maintenance_due_date_fails_init():
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("尽快处理", "M-240713-08"))
        db.commit()

    try:
        init_db()
    except RuntimeError as exc:
        assert "Cannot normalize legacy maintenance values" in str(exc)
        assert "M-240713-08" in str(exc)
    else:
        raise AssertionError("unrecognized legacy maintenance due date should fail init")



def test_legacy_iso_due_before_created_date_fails_init():
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("2026-07-12", "M-240713-08"))
        db.commit()

    try:
        init_db()
    except RuntimeError as exc:
        assert "Cannot normalize legacy maintenance values" in str(exc)
        assert "M-240713-08" in str(exc)
    else:
        raise AssertionError("legacy maintenance due date before created date should fail init")



def test_legacy_relative_due_date_requires_valid_created_date():
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET created_at = ?, due_at = ? WHERE id = ?", ("bad-date", "明日 18:00", "M-240713-08"))
        db.commit()

    try:
        init_db()
    except RuntimeError as exc:
        assert "Cannot normalize legacy maintenance values" in str(exc)
        assert "M-240713-08" in str(exc)
    else:
        raise AssertionError("legacy relative due date with invalid created date should fail init")



def test_non_text_legacy_maintenance_dates_fail_init():
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET created_at = ?, due_at = ? WHERE id = ?", (sqlite3.Binary(b"bad-date"), sqlite3.Binary(b"12345"), "M-240713-08"))
        db.commit()

    try:
        init_db()
    except RuntimeError as exc:
        assert "Cannot normalize legacy maintenance values" in str(exc)
        assert "M-240713-08" in str(exc)
    else:
        raise AssertionError("non-text legacy maintenance dates should fail init")



def test_legacy_month_day_due_date_is_normalized(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("07-16", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["due_at"] == "2026-07-16"



def test_legacy_month_day_due_date_rolls_forward_to_next_year(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET created_at = ?, due_at = ? WHERE id = ?", ("2026-12-31", "01-01", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["due_at"] == "2027-01-01"



def test_legacy_compact_iso_due_date_is_normalized(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("20260716", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["due_at"] == "2026-07-16"



def test_legacy_resolved_done_due_date_is_normalized(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("已完成", "M-240711-11"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240711-11")
    assert order["status"] == "resolved"
    assert order["due_at"] == order["created_at"]



def test_legacy_waiting_status_with_obsolete_guard_is_normalized(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_status_transition_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_non_open_update_guard")
        db.execute(
            """
            CREATE TRIGGER maintenance_orders_non_open_update_guard
            BEFORE UPDATE ON maintenance_orders
            WHEN OLD.status != 'open'
            BEGIN
                SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_STATUS');
            END;
            """
        )
        db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("waiting", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["status"] == "open"



def test_legacy_waiting_status_is_normalized(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_status_transition_guard")
        db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("waiting", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["status"] == "open"



def test_legacy_relative_maintenance_due_date_offsets_and_restores_trigger(client, admin_token):
    from app.database import init_db

    with get_connection() as db:
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_payload_update_guard")
        db.execute("DROP TRIGGER IF EXISTS maintenance_orders_immutable_update_guard")
        db.execute("UPDATE maintenance_orders SET due_at = ? WHERE id = ?", ("明日 18:00", "M-240713-08"))
        db.commit()

    init_db()

    response = client.get("/api/maintenance-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    order = next(item for item in response.json()["items"] if item["id"] == "M-240713-08")
    assert order["due_at"] == "2026-07-14"
    with get_connection() as db:
        triggers = {
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name IN (?, ?, ?)",
                (
                    "maintenance_orders_payload_update_guard",
                    "maintenance_orders_status_transition_guard",
                    "maintenance_orders_immutable_update_guard",
                ),
            ).fetchall()
        }
    assert triggers == {
        "maintenance_orders_payload_update_guard",
        "maintenance_orders_status_transition_guard",
        "maintenance_orders_immutable_update_guard",
    }



def test_invalid_maintenance_due_date_is_rejected(client, admin_token):
    response = client.post(
        "/api/maintenance-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**MAINTENANCE_PAYLOAD, "id": "M-BAD-DATE", "due_at": "not-a-date"},
    )

    assert response.status_code == 422



def test_direct_invalid_maintenance_date_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("M-BAD-DIRECT", "P-1202", "直写工单", "A-1202", "测试租客", "水电", "medium", "open", "未分配", "2026-02-30", "2026-07-16"),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid maintenance date should be blocked")



def test_create_maintenance_order_due_before_created_date_is_rejected(client, admin_token):
    response = client.post(
        "/api/maintenance-orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**MAINTENANCE_PAYLOAD, "id": "M-PAST-DUE", "due_at": "2026-07-14"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_MAINTENANCE_PAYLOAD"



def test_direct_maintenance_due_before_created_date_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("M-PAST-DIRECT", "P-1202", "直写工单", "A-1202", "测试租客", "水电", "medium", "open", "未分配", "2026-07-16", "2026-07-15"),
            )
        except sqlite3.DatabaseError as exc:
            assert "INVALID_MAINTENANCE_PAYLOAD" in str(exc)
        else:
            raise AssertionError("maintenance due date before created date should be blocked")
