import pytest

from app.database import get_connection


PROPERTY_PAYLOAD = {
    "id": "P-9901",
    "building": "Z 栋",
    "room": "9901",
    "layout": "两室一厅",
    "area": 72.5,
    "rent": 6800,
    "status": "vacant",
    "tenant": None,
    "lease_end": None,
    "tags": ["南向", "可看房"],
}


def test_viewer_can_list_properties(client, viewer_token):
    response = client.get("/api/properties", headers={"Authorization": f"Bearer {viewer_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["items"]


def test_admin_can_create_property(client, admin_token):
    response = client.post("/api/properties", headers={"Authorization": f"Bearer {admin_token}"}, json=PROPERTY_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "P-9901"
    assert body["tags"] == ["南向", "可看房"]

    list_response = client.get("/api/properties", headers={"Authorization": f"Bearer {admin_token}"})
    assert "P-9901" in {item["id"] for item in list_response.json()["items"]}


def test_create_duplicate_property_returns_conflict(client, admin_token):
    response = client.post("/api/properties", headers={"Authorization": f"Bearer {admin_token}"}, json={**PROPERTY_PAYLOAD, "id": "P-1201"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ALREADY_EXISTS"


def test_create_duplicate_room_returns_conflict(client, admin_token):
    response = client.post("/api/properties", headers={"Authorization": f"Bearer {admin_token}"}, json={**PROPERTY_PAYLOAD, "id": "P-9902", "building": "A 栋", "room": "1201"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ROOM_ALREADY_EXISTS"


def test_create_with_non_list_tags_returns_validation_error(client, admin_token):
    response = client.post("/api/properties", headers={"Authorization": f"Bearer {admin_token}"}, json={**PROPERTY_PAYLOAD, "tags": "南向"})

    assert response.status_code == 422


def test_admin_can_update_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200

    response = client.put(
        "/api/properties/P-9901",
        headers=headers,
        json={
            "building": "Z 栋",
            "room": "9901",
            "layout": "三室一厅",
            "area": 95.0,
            "rent": 9200,
            "status": "reserved",
            "tenant": "张三",
            "lease_end": "2027-07-15",
            "tags": ["已预约", "大户型"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rent"] == 9200
    assert body["status"] == "reserved"
    assert body["tags"] == ["已预约", "大户型"]

    list_response = client.get("/api/properties", headers=headers)
    updated = next(item for item in list_response.json()["items"] if item["id"] == "P-9901")
    assert updated["rent"] == 9200


def test_cannot_update_referenced_property_room(client, admin_token):
    response = client.put(
        "/api/properties/P-1201",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "building": "Z 栋",
            "room": "9901",
            "layout": "三室一厅",
            "area": 95.0,
            "rent": 9200,
            "status": "vacant",
            "tenant": None,
            "lease_end": None,
            "tags": ["大户型"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_HAS_RELATED_RECORDS"


def test_cannot_update_property_room_with_related_property_id(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("T-STALE", "P-9901", "测试租客", "13800000000", "Z-9901", "C-STALE", "paid", "2026-01-01", "2027-01-01", 0),
        )
        db.commit()

    response = client.put("/api/properties/P-9901", headers=headers, json={**{k: v for k, v in PROPERTY_PAYLOAD.items() if k != "id"}, "room": "9902"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_HAS_RELATED_RECORDS"


def test_direct_referenced_property_room_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET room = ?, room_key = ? WHERE id = ?", ("9999", "A-9999", "P-1201"))
        except Exception as exc:
            assert "PROPERTY_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("referenced property room update should be blocked")


def test_direct_invalid_property_relationship_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET tenant = ? WHERE id = ?", ("错误租客", "P-1202"))
        except Exception as exc:
            assert "INVALID_PROPERTY_RELATIONSHIP" in str(exc)
        else:
            raise AssertionError("vacant property should not keep tenant fields")


def test_direct_invalid_property_payload_is_blocked_by_database_trigger():
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P-PAYLOAD", "D 栋", "9913", "D-9913", "一室一厅", 45, 4200, "vacant", None, None, "[]"),
        )
        for field, value in (
            ("area", 0),
            ("rent", -1),
            ("tags_json", "not-json"),
        ):
            try:
                db.execute(f"UPDATE properties SET {field} = ? WHERE id = ?", (value, "P-PAYLOAD"))
            except Exception as exc:
                assert "INVALID_PROPERTY_PAYLOAD" in str(exc)
            else:
                raise AssertionError("invalid property payload should be blocked")

        try:
            db.execute(
                """
                INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("P-BAD-DATE", "D 栋", "9914", "D-9914", "一室一厅", 45, 4200, "reserved", "测试租客", "2026-02-30", "[]"),
            )
        except Exception as exc:
            assert "INVALID_PROPERTY_PAYLOAD" in str(exc)
        else:
            raise AssertionError("invalid property lease_end should be blocked")


def test_direct_reserved_property_without_tenant_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET status = ?, tenant = NULL, lease_end = NULL WHERE id = ?", ("reserved", "P-1202"))
        except Exception as exc:
            assert "INVALID_PROPERTY_RELATIONSHIP" in str(exc)
        else:
            raise AssertionError("reserved property should require tenant and lease end")


def test_direct_invalid_property_status_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET status = ? WHERE id = ?", ("invalid", "P-1202"))
        except Exception as exc:
            assert "INVALID_PROPERTY_RELATIONSHIP" in str(exc)
        else:
            raise AssertionError("invalid property status should be blocked")


def test_direct_maintenance_property_with_tenant_is_blocked_by_database_trigger():
    with get_connection() as db:
        try:
            db.execute("UPDATE properties SET tenant = ?, lease_end = ? WHERE id = ?", ("错误租客", "2027-07-15", "P-0806"))
        except Exception as exc:
            assert "INVALID_PROPERTY_RELATIONSHIP" in str(exc)
        else:
            raise AssertionError("maintenance property should not keep tenant fields")


def test_direct_contract_only_property_relationship_update_is_blocked_by_database_trigger():
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P-9910", "D 栋", "9910", "D-9910", "一室一厅", 45, 4200, "vacant", None, None, "[]"),
        )
        db.execute(
            """
            INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("C-9910", "P-9910", "合同租客", "D-9910", "2026-07-15", "2027-07-15", 4200, 4200, "pending", 365),
        )
        try:
            db.execute("UPDATE properties SET status = ?, tenant = ?, lease_end = ? WHERE id = ?", ("reserved", "合同租客", "2027-07-15", "P-9910"))
        except Exception as exc:
            assert "PROPERTY_HAS_RELATED_RECORDS" in str(exc)
        else:
            raise AssertionError("contract-only referenced property relationship update should be blocked")


@pytest.mark.parametrize(
    "field_update",
    [
        {"status": "vacant", "tenant": None, "lease_end": None},
        {"status": "reserved", "tenant": "李四", "lease_end": "2027-08-01"},
        {"status": "occupied", "tenant": "李四", "lease_end": "2027-03-18"},
    ],
)
def test_cannot_update_referenced_property_relationship_fields_without_room_change(client, admin_token, field_update):
    payload = {
        "building": "A 栋",
        "room": "1201",
        "layout": "三室一厅",
        "area": 95.0,
        "rent": 9200,
        "status": "occupied",
        "tenant": "林思远",
        "lease_end": "2027-03-18",
        "tags": ["大户型"],
        **field_update,
    }

    response = client.put("/api/properties/P-1201", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_HAS_RELATED_RECORDS"


def test_can_update_referenced_property_non_relationship_fields_without_room_change(client, admin_token):
    response = client.put(
        "/api/properties/P-1201",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "building": "A 栋",
            "room": "1201",
            "layout": "精装三室一厅",
            "area": 96.0,
            "rent": 9300,
            "status": "occupied",
            "tenant": "林思远",
            "lease_end": "2027-03-18",
            "tags": ["大户型", "精装"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["layout"] == "精装三室一厅"
    assert body["area"] == 96.0
    assert body["rent"] == 9300
    assert body["tags"] == ["大户型", "精装"]


def test_update_to_duplicate_room_returns_conflict(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200

    response = client.put("/api/properties/P-9901", headers=headers, json={**{k: v for k, v in PROPERTY_PAYLOAD.items() if k != "id"}, "building": "A 栋", "room": "1201"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_ROOM_ALREADY_EXISTS"


def test_update_missing_property_returns_not_found(client, admin_token):
    response = client.put(
        "/api/properties/missing",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={k: v for k, v in PROPERTY_PAYLOAD.items() if k != "id"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_cannot_delete_referenced_property(client, admin_token):
    response = client.delete("/api/properties/P-1201", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_HAS_RELATED_RECORDS"


@pytest.mark.parametrize(
    ("table", "values"),
    [
        ("tenants", ("T-999", "P-9901", "测试租客", "13800000000", "Z-9901", "C-999", "paid", "2026-01-01", "2027-01-01", 0, "active", None)),
        ("contracts", ("C-999", "P-9901", "测试租客", "Z-9901", "2026-01-01", "2027-01-01", 6800, 6800, "pending", 180)),
        ("maintenance_orders", ("M-999", "P-9901", "测试工单", "Z-9901", "测试租客", "水电", "low", "open", "维修人员", "2026-01-01", "2026-01-02")),
        ("finance_transactions", ("F-999", "P-9901", "2026-01-01", "租金", "Z-9901", "测试租客", 6800, "银行转账", "paid", "测试", None, None, None)),
    ],
)
def test_cannot_delete_property_with_related_table_record(client, admin_token, table, values):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200

    placeholders = ", ".join("?" for _ in values)
    with get_connection() as db:
        db.execute(f"INSERT INTO {table} VALUES ({placeholders})", values)
        db.commit()

    response = client.delete("/api/properties/P-9901", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROPERTY_HAS_RELATED_RECORDS"


def test_admin_can_delete_unreferenced_property(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200

    response = client.delete("/api/properties/P-9901", headers=headers)

    assert response.status_code == 204

    list_response = client.get("/api/properties", headers=headers)
    assert "P-9901" not in {item["id"] for item in list_response.json()["items"]}


def test_delete_missing_property_returns_not_found(client, admin_token):
    response = client.delete("/api/properties/missing", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPERTY_NOT_FOUND"


def test_viewer_cannot_mutate_properties(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}

    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    update_response = client.put("/api/properties/P-1201", headers=headers, json={k: v for k, v in PROPERTY_PAYLOAD.items() if k != "id"})
    delete_response = client.delete("/api/properties/P-1201", headers=headers)

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_leasing_can_create_and_update_but_not_delete(client):
    token_response = client.post("/api/auth/login", json={"username": "leasing", "password": "leasing123"})
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    update_response = client.put("/api/properties/P-9901", headers=headers, json={**{k: v for k, v in PROPERTY_PAYLOAD.items() if k != "id"}, "rent": 7000})
    delete_response = client.delete("/api/properties/P-9901", headers=headers)

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert delete_response.status_code == 403


def test_moved_out_tenant_history_does_not_block_property_delete(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post("/api/properties", headers=headers, json=PROPERTY_PAYLOAD)
    assert create_response.status_code == 200

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance, status, move_out_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("T-MOVED-HISTORY", "P-9901", "历史租客", "13800000000", "Z-9901", "C-MOVED-HISTORY", "paid", "2026-01-01", "2026-06-01", 0, "moved_out", "2026-06-01"),
        )
        db.commit()

    response = client.delete("/api/properties/P-9901", headers=headers)

    assert response.status_code == 204
