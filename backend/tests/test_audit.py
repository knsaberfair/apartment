from datetime import datetime, timedelta, timezone
from urllib.parse import quote


def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def create_property(client, headers, property_id, room):
    return client.post(
        "/api/properties",
        headers=headers,
        json={"id": property_id, "building": "Z 栋", "room": room, "layout": "一室一厅", "area": 40, "rent": 3000, "status": "vacant", "tags": []},
    )


def test_core_mutation_writes_audit_log(client, admin_token):
    headers = admin_headers(admin_token)

    create_response = create_property(client, headers, "P-AUDIT", "0101")
    logs_response = client.get("/api/audit-logs", headers=headers)

    assert create_response.status_code == 200
    assert logs_response.status_code == 200
    body = logs_response.json()
    assert body["total"] >= 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    log = body["items"][0]
    assert log["actor_id"] == "demo-super-admin"
    assert log["action"] == "create"
    assert log["resource_type"] == "property"
    assert log["resource_id"] == "P-AUDIT"


def test_viewer_cannot_read_audit_logs(client, viewer_token):
    response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 403


def test_audit_logs_support_pagination(client, admin_token):
    headers = admin_headers(admin_token)
    for index in range(3):
        response = create_property(client, headers, f"P-AUDIT-PAGE-{index}", f"02{index}")
        assert response.status_code == 200

    first_page = client.get("/api/audit-logs?limit=2&offset=0", headers=headers)
    second_page = client.get("/api/audit-logs?limit=2&offset=2", headers=headers)

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first_body = first_page.json()
    second_body = second_page.json()
    assert first_body["total"] >= 3
    assert first_body["limit"] == 2
    assert first_body["offset"] == 0
    assert len(first_body["items"]) == 2
    assert second_body["items"]
    assert {item["id"] for item in first_body["items"]}.isdisjoint({item["id"] for item in second_body["items"]})


def test_audit_logs_support_filters(client, admin_token):
    headers = admin_headers(admin_token)
    create_response = create_property(client, headers, "P-AUDIT-FILTER", "0301")
    assert create_response.status_code == 200
    update_response = client.put(
        "/api/properties/P-AUDIT-FILTER",
        headers=headers,
        json={"building": "Z 栋", "room": "0301", "layout": "两室一厅", "area": 55, "rent": 3600, "status": "vacant", "tags": ["筛选"]},
    )
    assert update_response.status_code == 200

    filtered = client.get("/api/audit-logs?action=update&resource_type=property&resource_id=P-AUDIT-FILTER", headers=headers)
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "update"
    assert body["items"][0]["resource_id"] == "P-AUDIT-FILTER"

    actor_filtered = client.get("/api/audit-logs?actor_id=demo-super-admin&q=P-AUDIT-FILTER", headers=headers)
    assert actor_filtered.status_code == 200
    assert actor_filtered.json()["total"] >= 2
    assert all(item["actor_id"] == "demo-super-admin" for item in actor_filtered.json()["items"])


def test_audit_logs_support_time_range_filter(client, admin_token):
    headers = admin_headers(admin_token)
    response = create_property(client, headers, "P-AUDIT-TIME", "0401")
    assert response.status_code == 200

    latest = client.get("/api/audit-logs?resource_id=P-AUDIT-TIME", headers=headers).json()["items"][0]
    created_at = quote(latest["created_at"], safe="")
    in_range = client.get(f"/api/audit-logs?created_from={created_at}&created_to={created_at}", headers=headers)
    utc_created_at = datetime.fromisoformat(latest["created_at"])
    offset_created_at = quote(utc_created_at.astimezone(timezone(timedelta(hours=8))).isoformat(), safe="")
    offset_range = client.get(f"/api/audit-logs?created_from={offset_created_at}&created_to={offset_created_at}", headers=headers)
    naive_datetime = client.get("/api/audit-logs?created_from=2026-07-17T00:00:00", headers=headers)
    invalid_range = client.get("/api/audit-logs?created_from=2026-07-18T00:00:00%2B00:00&created_to=2026-07-17T00:00:00%2B00:00", headers=headers)
    invalid_datetime = client.get("/api/audit-logs?created_from=not-a-date", headers=headers)

    assert in_range.status_code == 200
    assert any(item["resource_id"] == "P-AUDIT-TIME" for item in in_range.json()["items"])
    assert offset_range.status_code == 200
    assert any(item["resource_id"] == "P-AUDIT-TIME" for item in offset_range.json()["items"])
    assert naive_datetime.status_code == 422
    assert invalid_range.status_code == 422
    assert invalid_datetime.status_code == 422


def test_audit_logs_reject_invalid_direct_inserts():
    from app.database import get_connection

    with get_connection() as db:
        for values in (
            ("", "Admin", "super_admin", "create", "property", "P-1", "2026-07-16T00:00:00+00:00"),
            ("demo-super-admin", "Admin", "super_admin", "", "property", "P-1", "2026-07-16T00:00:00+00:00"),
            ("demo-super-admin", "Admin", "super_admin", "create", "property", "P-1", "2026-02-30T00:00:00.000000+00:00"),
            ("demo-super-admin", "Admin", "super_admin", "create", "property", "P-1", "2026-07-16garbage"),
            ("demo-super-admin", "Admin", "super_admin", "create", "property", "P-1", "2026-07-16T00:00:00garbage+00:00"),
        ):
            try:
                db.execute(
                    """
                    INSERT INTO audit_logs (actor_id, actor_name, actor_role, action, resource_type, resource_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            except Exception as exc:
                assert "INVALID_AUDIT_LOG_PAYLOAD" in str(exc)
            else:
                raise AssertionError("invalid audit log insert should be blocked")


def test_audit_logs_are_append_only(client, admin_token):
    from app.database import get_connection

    headers = admin_headers(admin_token)
    create_response = create_property(client, headers, "P-AUDIT-IMMUTABLE", "0102")
    assert create_response.status_code == 200

    with get_connection() as db:
        log_id = db.execute("SELECT id FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()["id"]
        try:
            db.execute("UPDATE audit_logs SET action = ? WHERE id = ?", ("tamper", log_id))
        except Exception as exc:
            assert "AUDIT_LOG_IMMUTABLE" in str(exc)
        else:
            raise AssertionError("audit log update should be blocked")

        try:
            db.execute("DELETE FROM audit_logs WHERE id = ?", (log_id,))
        except Exception as exc:
            assert "AUDIT_LOG_IMMUTABLE" in str(exc)
        else:
            raise AssertionError("audit log delete should be blocked")
