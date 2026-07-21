import calendar
from datetime import date, datetime, timezone
import csv
import hashlib
import io
import json
import sqlite3
from typing import Any

def _rows(db: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(f"SELECT * FROM {table}").fetchall()]


def _insert_audit_log(db: sqlite3.Connection, actor: dict[str, Any] | None, action: str, resource_type: str, resource_id: str) -> sqlite3.Cursor:
    actor = actor or {}
    return db.execute(
        """
        INSERT INTO audit_logs (actor_id, actor_name, actor_role, action, resource_type, resource_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.get("id") or "unknown",
            actor.get("name") or "unknown",
            actor.get("role") or "unknown",
            action,
            resource_type,
            resource_id,
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        ),
    )


def _audit_if_requested(db: sqlite3.Connection, actor: dict[str, Any] | None, action: str, resource_type: str, resource_id: str) -> None:
    if actor is not None:
        _insert_audit_log(db, actor, action, resource_type, resource_id)


def create_audit_log(db: sqlite3.Connection, actor: dict[str, Any], action: str, resource_type: str, resource_id: str) -> dict[str, Any]:
    with db:
        cursor = _insert_audit_log(db, actor, action, resource_type, resource_id)
    row = db.execute("SELECT * FROM audit_logs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_audit_logs(db: sqlite3.Connection, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return [dict(row) for row in rows]


def _contains_clause(columns: list[str], keyword: str, params: list[Any]) -> str:
    pattern = f"%{keyword.strip().lower()}%"
    params.extend([pattern] * len(columns))
    return "(" + " OR ".join(f"LOWER(CAST({column} AS TEXT)) LIKE ?" for column in columns) + ")"


def _page_query(
    db: sqlite3.Connection,
    table: str,
    search_columns: list[str],
    order_by: str,
    limit: int,
    offset: int,
    q: str | None = None,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if q and q.strip():
        clauses.append(_contains_clause(search_columns, q, params))
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(f"SELECT COUNT(*) AS count FROM {table}{where_sql}", params).fetchone()["count"]
    rows = db.execute(
        f"SELECT * FROM {table}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total}


def _filter_items(items: list[dict[str, Any]], q: str | None, fields: list[str]) -> list[dict[str, Any]]:
    keyword = q.strip().lower() if q else ""
    if not keyword:
        return items
    return [item for item in items if any(keyword in str(item.get(field) or "").lower() for field in fields)]


def list_audit_logs_page(
    db: sqlite3.Connection,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    if q and q.strip():
        clauses.append(
            _contains_clause(
                ["id", "actor_id", "actor_name", "actor_role", "action", "resource_type", "resource_id", "created_at"],
                q,
                params,
            ),
        )
    for column, value in (
        ("actor_id", actor_id),
        ("actor_role", actor_role),
        ("action", action),
        ("resource_type", resource_type),
        ("resource_id", resource_id),
    ):
        if value and value.strip():
            clauses.append(f"{column} = ?")
            params.append(value.strip())
    if created_from:
        clauses.append("created_at >= ?")
        params.append(created_from)
    if created_to:
        clauses.append("created_at <= ?")
        params.append(created_to)

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(f"SELECT COUNT(*) AS count FROM audit_logs{where_sql}", params).fetchone()["count"]
    rows = db.execute(
        f"SELECT * FROM audit_logs{where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total}


def _property_from_row(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["tags"] = json.loads(item.pop("tags_json") or "[]")
    return item


def _property_values(property_data: dict[str, Any]) -> dict[str, Any]:
    return {
        **property_data,
        "room_key": _property_room_key(property_data),
        "tags_json": json.dumps(property_data.get("tags", []), ensure_ascii=False),
    }


def _property_room_key(property_item: dict[str, Any]) -> str:
    building = property_item["building"].replace(" 栋", "").replace("栋", "").strip()
    return f"{building}-{property_item['room']}"


def _property_with_same_room(db: sqlite3.Connection, property_data: dict[str, Any], excluded_id: str | None = None) -> dict[str, Any] | None:
    room_key = _property_room_key(property_data)
    for item in list_properties(db):
        if item["id"] != excluded_id and _property_room_key(item) == room_key:
            return item
    return None


def _raise_property_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    if "INVALID_PROPERTY_PAYLOAD" in message or "INVALID_PROPERTY_RELATIONSHIP" in message or "INVALID_PROPERTY_ROOM_KEY" in message or "PROPERTY_TENANT_REQUIRED" in message:
        raise KeyError("INVALID_PROPERTY_PAYLOAD") from exc
    if "properties.room_key" in message:
        raise KeyError("PROPERTY_ROOM_ALREADY_EXISTS") from exc
    if "properties.id" in message:
        raise KeyError("PROPERTY_ALREADY_EXISTS") from exc
    if "PROPERTY_HAS_RELATED_RECORDS" in message:
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS") from exc
    raise exc


def _property_has_related_records(db: sqlite3.Connection, property_item: dict[str, Any]) -> bool:
    if property_item["status"] != "vacant" or property_item["tenant"] or property_item["lease_end"]:
        return True

    room_key = _property_room_key(property_item)
    if db.execute("SELECT 1 FROM tenants WHERE (property_id = ? OR room = ?) AND status = 'active' LIMIT 1", (property_item["id"], room_key)).fetchone():
        return True
    for table in ("contracts", "maintenance_orders", "finance_transactions"):
        if db.execute(f"SELECT 1 FROM {table} WHERE property_id = ? OR room = ? LIMIT 1", (property_item["id"], room_key)).fetchone():
            return True
    return False


def list_properties(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM properties ORDER BY building, room, id").fetchall()
    return [_property_from_row(row) for row in rows if row is not None]


def list_properties_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    page = _page_query(
        db,
        "properties",
        ["id", "building", "room", "layout", "status", "tenant", "lease_end", "tags_json", "area", "rent"],
        "building, room, id",
        limit,
        offset,
        q,
    )
    return {"items": [_property_from_row(item) for item in page["items"] if item is not None], "total": page["total"]}


def get_property(db: sqlite3.Connection, property_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    return _property_from_row(row)


def create_property(db: sqlite3.Connection, property_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    if get_property(db, property_data["id"]):
        raise KeyError("PROPERTY_ALREADY_EXISTS")
    if _property_with_same_room(db, property_data):
        raise KeyError("PROPERTY_ROOM_ALREADY_EXISTS")

    values = _property_values(property_data)
    try:
        with db:
            db.execute(
                """
                INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
                VALUES (:id, :building, :room, :room_key, :layout, :area, :rent, :status, :tenant, :lease_end, :tags_json)
                """,
                values,
            )
            _audit_if_requested(db, actor, "create", "property", values["id"])
    except sqlite3.IntegrityError as exc:
        _raise_property_integrity_error(exc)
    created = get_property(db, property_data["id"])
    if not created:
        raise KeyError("PROPERTY_NOT_FOUND")
    return created


def update_property(db: sqlite3.Connection, property_id: str, property_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = get_property(db, property_id)
    if not existing:
        raise KeyError("PROPERTY_NOT_FOUND")
    if _property_with_same_room(db, property_data, excluded_id=property_id):
        raise KeyError("PROPERTY_ROOM_ALREADY_EXISTS")
    has_related_records = _property_has_related_records(db, existing)
    if _property_room_key(existing) != _property_room_key(property_data) and has_related_records:
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS")
    if has_related_records and any(existing[key] != property_data[key] for key in ("status", "tenant", "lease_end")):
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS")

    values = {**_property_values(property_data), "id": property_id}
    try:
        with db:
            db.execute(
                """
                UPDATE properties
                SET building = :building,
                    room = :room,
                    room_key = :room_key,
                    layout = :layout,
                    area = :area,
                    rent = :rent,
                    status = :status,
                    tenant = :tenant,
                    lease_end = :lease_end,
                    tags_json = :tags_json
                WHERE id = :id
                """,
                values,
            )
            _audit_if_requested(db, actor, "update", "property", property_id)
    except sqlite3.IntegrityError as exc:
        _raise_property_integrity_error(exc)
    updated = get_property(db, property_id)
    if not updated:
        raise KeyError("PROPERTY_NOT_FOUND")
    return updated


def delete_property(db: sqlite3.Connection, property_id: str, actor: dict[str, Any] | None = None) -> None:
    property_item = get_property(db, property_id)
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    if _property_has_related_records(db, property_item):
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS")

    try:
        with db:
            db.execute("DELETE FROM tenants WHERE property_id = ? AND status != 'active'", (property_id,))
            db.execute("DELETE FROM properties WHERE id = ?", (property_id,))
            _audit_if_requested(db, actor, "delete", "property", property_id)
    except sqlite3.IntegrityError as exc:
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS") from exc


def list_tenants(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(db, "tenants")


def list_tenants_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    return _page_query(
        db,
        "tenants",
        ["id", "property_id", "name", "phone", "room", "contract_id", "payment_status", "move_in_date", "lease_end", "balance", "status", "move_out_date"],
        "id",
        limit,
        offset,
        q,
    )


def get_tenant(db: sqlite3.Connection, tenant_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    return dict(row) if row else None


def _tenant_values(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> dict[str, Any]:
    property_item = get_property(db, tenant_data["property_id"])
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    return {**tenant_data, "room": _property_room_key(property_item), "status": tenant_data.get("status", "active"), "move_out_date": tenant_data.get("move_out_date")}


def _property_available_for_tenant(db: sqlite3.Connection, property_id: str, tenant_id: str | None = None) -> bool:
    property_item = get_property(db, property_id)
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    tenant = db.execute("SELECT id FROM tenants WHERE property_id = ? AND status = 'active' LIMIT 1", (property_id,)).fetchone()
    if tenant and tenant["id"] != tenant_id:
        return False
    if property_item["status"] != "vacant" and (tenant_id is None or not tenant or tenant["id"] != tenant_id):
        return False
    return True


def _tenant_has_contracts(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> bool:
    return db.execute(
        "SELECT 1 FROM contracts WHERE id = ? OR property_id = ? OR room = ? LIMIT 1",
        (tenant_data["contract_id"], tenant_data["property_id"], tenant_data["room"]),
    ).fetchone() is not None


def _tenant_contract_identity_conflicts(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> bool:
    return db.execute(
        """
        SELECT 1
        FROM contracts
        WHERE status != 'terminated'
          AND (id = ? OR property_id = ? OR room = ?)
          AND NOT (id = ? AND property_id = ? AND room = ? AND tenant = ?)
        LIMIT 1
        """,
        (
            tenant_data["contract_id"],
            tenant_data["property_id"],
            tenant_data["room"],
            tenant_data["contract_id"],
            tenant_data["property_id"],
            tenant_data["room"],
            tenant_data["name"],
        ),
    ).fetchone() is not None


def _tenant_has_activity_records(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> bool:
    values = (tenant_data["property_id"], tenant_data["room"], tenant_data["name"])
    return any(
        db.execute(
            f"SELECT 1 FROM {table} WHERE property_id = ? OR room = ? OR tenant = ? LIMIT 1",
            values,
        ).fetchone()
        is not None
        for table in ("maintenance_orders", "finance_transactions")
    )


def _sync_tenant_property(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> None:
    db.execute(
        """
        UPDATE properties
        SET tenant = ?, lease_end = ?, status = 'occupied'
        WHERE id = ?
        """,
        (tenant_data["name"], tenant_data["lease_end"], tenant_data["property_id"]),
    )


def _clear_tenant_property(db: sqlite3.Connection, tenant_data: dict[str, Any]) -> None:
    if db.execute("SELECT 1 FROM tenants WHERE property_id = ? AND status = 'active' LIMIT 1", (tenant_data["property_id"],)).fetchone():
        return
    db.execute(
        """
        UPDATE properties
        SET tenant = NULL, lease_end = NULL, status = 'vacant'
        WHERE id = ?
        """,
        (tenant_data["property_id"],),
    )


def _is_tenant_property_unique_error(exc: sqlite3.IntegrityError) -> bool:
    message = str(exc)
    return "tenants.property_id" in message or "idx_tenants_property_id" in message


def _raise_tenant_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    for code in ("TENANT_HAS_RELATED_CONTRACTS", "TENANT_HAS_CONTRACTS", "TENANT_HAS_RELATED_RECORDS"):
        if code in message:
            raise KeyError(code) from exc
    if "PROPERTY_ALREADY_OCCUPIED" in message or _is_tenant_property_unique_error(exc):
        raise KeyError("PROPERTY_ALREADY_OCCUPIED") from exc
    if "RELATED_PROPERTY_REQUIRED" in message or "FOREIGN KEY" in message.upper():
        raise KeyError("PROPERTY_NOT_FOUND") from exc
    if "INVALID_PROPERTY_ROOM_KEY" in message:
        raise KeyError("PROPERTY_ROOM_INVALID") from exc
    raise exc


def create_tenant(db: sqlite3.Connection, tenant_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if get_tenant(db, tenant_data["id"]):
                raise KeyError("TENANT_ALREADY_EXISTS")
            if not _property_available_for_tenant(db, tenant_data["property_id"]):
                raise KeyError("PROPERTY_ALREADY_OCCUPIED")
            values = _tenant_values(db, tenant_data)
            if _tenant_contract_identity_conflicts(db, values):
                raise KeyError("TENANT_HAS_CONTRACTS")
            db.execute(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance, status, move_out_date)
                VALUES (:id, :property_id, :name, :phone, :room, :contract_id, :payment_status, :move_in_date, :lease_end, :balance, :status, :move_out_date)
                """,
                values,
            )
            _sync_tenant_property(db, values)
            _audit_if_requested(db, actor, "create", "tenant", values["id"])
    except sqlite3.IntegrityError as exc:
        if "tenants.id" in str(exc):
            raise KeyError("TENANT_ALREADY_EXISTS") from exc
        _raise_tenant_integrity_error(exc)
    created = get_tenant(db, tenant_data["id"])
    if not created:
        raise KeyError("TENANT_NOT_FOUND")
    return created


def update_tenant(db: sqlite3.Connection, tenant_id: str, tenant_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            existing = get_tenant(db, tenant_id)
            if not existing:
                raise KeyError("TENANT_NOT_FOUND")
            identity_changed = any(existing[key] != tenant_data[key] for key in ("name", "contract_id", "property_id"))
            if identity_changed and _tenant_has_contracts(db, existing):
                raise KeyError("TENANT_HAS_CONTRACTS")
            if identity_changed and _tenant_has_activity_records(db, existing):
                raise KeyError("TENANT_HAS_RELATED_RECORDS")
            if not _property_available_for_tenant(db, tenant_data["property_id"], tenant_id):
                raise KeyError("PROPERTY_ALREADY_OCCUPIED")
            values = {**_tenant_values(db, tenant_data), "id": tenant_id}
            if identity_changed and _tenant_contract_identity_conflicts(db, values):
                raise KeyError("TENANT_HAS_CONTRACTS")
            should_clear_previous_property = existing["property_id"] != values["property_id"] or existing["name"] != values["name"]
            db.execute(
                """
                UPDATE tenants
                SET property_id = :property_id,
                    name = :name,
                    phone = :phone,
                    room = :room,
                    contract_id = :contract_id,
                    payment_status = :payment_status,
                    move_in_date = :move_in_date,
                    lease_end = :lease_end,
                    balance = :balance,
                    status = :status,
                    move_out_date = :move_out_date
                WHERE id = :id
                """,
                values,
            )
            if should_clear_previous_property:
                _clear_tenant_property(db, existing)
            _sync_tenant_property(db, values)
            _audit_if_requested(db, actor, "update", "tenant", tenant_id)
    except sqlite3.IntegrityError as exc:
        _raise_tenant_integrity_error(exc)

    updated = get_tenant(db, tenant_id)
    if not updated:
        raise KeyError("TENANT_NOT_FOUND")
    return updated


def delete_tenant(db: sqlite3.Connection, tenant_id: str, actor: dict[str, Any] | None = None) -> None:
    try:
        with db:
            tenant = get_tenant(db, tenant_id)
            if not tenant:
                raise KeyError("TENANT_NOT_FOUND")
            if _tenant_has_contracts(db, tenant):
                raise KeyError("TENANT_HAS_RELATED_CONTRACTS")
            if _tenant_has_activity_records(db, tenant):
                raise KeyError("TENANT_HAS_RELATED_RECORDS")
            db.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
            _clear_tenant_property(db, tenant)
            _audit_if_requested(db, actor, "delete", "tenant", tenant_id)
    except sqlite3.IntegrityError as exc:
        _raise_tenant_integrity_error(exc)


def get_tenant_account_by_tenant_id(db: sqlite3.Connection, tenant_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM tenant_accounts WHERE tenant_id = ?", (tenant_id,)).fetchone()
    return dict(row) if row else None


def get_tenant_account_by_openid(db: sqlite3.Connection, openid: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM tenant_accounts WHERE openid = ?", (openid,)).fetchone()
    return dict(row) if row else None


def bind_tenant_account(
    db: sqlite3.Connection,
    tenant_id: str,
    openid: str,
    display_name: str,
    unionid: str | None = None,
) -> dict[str, Any]:
    tenant = get_tenant(db, tenant_id)
    if not tenant or tenant["status"] != "active":
        raise KeyError("TENANT_NOT_BOUND")
    existing_by_openid = get_tenant_account_by_openid(db, openid)
    if existing_by_openid and existing_by_openid["tenant_id"] != tenant_id:
        raise KeyError("TENANT_ACCOUNT_ALREADY_BOUND")

    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    existing_by_tenant = get_tenant_account_by_tenant_id(db, tenant_id)
    if existing_by_tenant and existing_by_tenant["openid"] != openid:
        raise KeyError("TENANT_ACCOUNT_ALREADY_BOUND")

    values = {
        "id": existing_by_tenant["id"] if existing_by_tenant else f"TA-{tenant_id}",
        "tenant_id": tenant_id,
        "openid": openid,
        "unionid": unionid,
        "display_name": display_name,
        "created_at": existing_by_tenant["created_at"] if existing_by_tenant else now,
        "last_login_at": now,
    }
    with db:
        db.execute(
            """
            INSERT INTO tenant_accounts (id, tenant_id, openid, unionid, display_name, created_at, last_login_at)
            VALUES (:id, :tenant_id, :openid, :unionid, :display_name, :created_at, :last_login_at)
            ON CONFLICT(tenant_id) DO UPDATE SET
                unionid = excluded.unionid,
                display_name = excluded.display_name,
                last_login_at = excluded.last_login_at
            """,
            values,
        )
    account = get_tenant_account_by_tenant_id(db, tenant_id)
    if not account:
        raise KeyError("TENANT_ACCOUNT_NOT_FOUND")
    return account


def touch_tenant_account(db: sqlite3.Connection, tenant_id: str) -> dict[str, Any]:
    account = get_tenant_account_by_tenant_id(db, tenant_id)
    if not account:
        raise KeyError("TENANT_NOT_BOUND")
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with db:
        db.execute("UPDATE tenant_accounts SET last_login_at = ? WHERE tenant_id = ?", (now, tenant_id))
    account = get_tenant_account_by_tenant_id(db, tenant_id)
    if not account:
        raise KeyError("TENANT_NOT_BOUND")
    return account


def list_tenant_contracts(db: sqlite3.Connection, tenant_id: str) -> list[dict[str, Any]]:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return []
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT * FROM contracts
            WHERE id = ?
            ORDER BY end_date DESC, id DESC
            """,
            (tenant["contract_id"],),
        ).fetchall()
    ]


def list_tenant_transactions(db: sqlite3.Connection, tenant_id: str) -> list[dict[str, Any]]:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return []
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT * FROM finance_transactions
            WHERE contract_id = ?
               OR (property_id = ? AND room = ? AND tenant = ?)
            ORDER BY date DESC, id DESC
            """,
            (tenant["contract_id"], tenant["property_id"], tenant["room"], tenant["name"]),
        ).fetchall()
    ]


def list_tenant_maintenance_orders(db: sqlite3.Connection, tenant_id: str) -> list[dict[str, Any]]:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return []
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT * FROM maintenance_orders
            WHERE property_id = ? AND room = ?
            ORDER BY created_at DESC, id DESC
            """,
            (tenant["property_id"], tenant["room"]),
        ).fetchall()
    ]


def get_tenant_transaction(db: sqlite3.Connection, tenant_id: str, transaction_id: str) -> dict[str, Any] | None:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return None
    row = db.execute(
        """
        SELECT * FROM finance_transactions
        WHERE id = ?
          AND (contract_id = ? OR (property_id = ? AND room = ? AND tenant = ?))
        """,
        (transaction_id, tenant["contract_id"], tenant["property_id"], tenant["room"], tenant["name"]),
    ).fetchone()
    return dict(row) if row else None


def pay_tenant_transaction(db: sqlite3.Connection, tenant_id: str, transaction_id: str, method: str = "微信支付", actor: dict[str, Any] | None = None) -> dict[str, Any]:
    transaction = get_tenant_transaction(db, tenant_id, transaction_id)
    if not transaction:
        raise KeyError("FINANCE_TRANSACTION_NOT_FOUND")
    if transaction["status"] not in {"pending", "overdue"}:
        raise KeyError("INVALID_FINANCE_STATUS")

    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE finance_transactions SET status = ?, method = ? WHERE id = ?", ("paid", method, transaction_id))
            _audit_if_requested(db, actor, "pay", "finance_transaction", transaction_id)
    except sqlite3.IntegrityError as exc:
        _raise_finance_integrity_error(exc)
    paid = get_tenant_transaction(db, tenant_id, transaction_id)
    if not paid:
        raise KeyError("FINANCE_TRANSACTION_NOT_FOUND")
    return paid


def _contract_from_row(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _contract_days_left(end_date: str) -> int:
    return max((date.fromisoformat(end_date) - date.today()).days, 0)


def _contract_values(db: sqlite3.Connection, contract_data: dict[str, Any], status: str = "pending") -> dict[str, Any]:
    property_item = get_property(db, contract_data["property_id"])
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    return {
        **contract_data,
        "room": _property_room_key(property_item),
        "status": status,
        "days_left": _contract_days_left(contract_data["end_date"]) if status != "terminated" else 0,
    }


def _raise_contract_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    if "move_outs.contract_id" in message or "idx_move_outs_contract_id" in message or "MOVE_OUT_ALREADY_EXISTS" in message:
        raise KeyError("MOVE_OUT_ALREADY_EXISTS") from exc
    if "deposit_settlements.move_out_id" in message or "idx_deposit_settlements_move_out_id" in message or "SETTLEMENT_ALREADY_EXISTS" in message:
        raise KeyError("SETTLEMENT_ALREADY_EXISTS") from exc
    if "LIFECYCLE_RECORD_DELETE_FORBIDDEN" in message or "LIFECYCLE_RECORD_UPDATE_FORBIDDEN" in message:
        raise KeyError("INVALID_CONTRACT_STATUS") from exc
    if "contracts.id" in message:
        raise KeyError("CONTRACT_ALREADY_EXISTS") from exc
    if "RELATED_PROPERTY_REQUIRED" in message or "FOREIGN KEY" in message.upper():
        raise KeyError("PROPERTY_NOT_FOUND") from exc
    if "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY" in message:
        raise KeyError("CONTRACT_ALREADY_EXISTS_FOR_PROPERTY") from exc
    if "TENANT_HAS_RELATED_CONTRACTS" in message:
        raise KeyError("TENANT_HAS_RELATED_CONTRACTS") from exc
    if "TENANT_HAS_CONTRACTS" in message:
        raise KeyError("TENANT_HAS_CONTRACTS") from exc
    if "INVALID_CONTRACT_PAYLOAD" in message:
        raise KeyError("INVALID_CONTRACT_PAYLOAD") from exc
    if "INVALID_CONTRACT_STATUS" in message:
        raise KeyError("INVALID_CONTRACT_STATUS") from exc
    if "RESERVED_FINANCE_TRANSACTION_ID" in message or "INVALID_FINANCE_PAYLOAD" in message or "FINANCE_TRANSACTION_DELETE_FORBIDDEN" in message:
        raise KeyError("INVALID_SETTLEMENT_PAYLOAD") from exc
    if "finance_transactions.id" in message:
        raise KeyError("SETTLEMENT_ALREADY_EXISTS") from exc
    if "CONTRACT_DELETE_FORBIDDEN" in message:
        raise KeyError("CONTRACT_DELETE_FORBIDDEN") from exc
    if "PROPERTY_HAS_RELATED_RECORDS" in message or "PROPERTY_TENANT_REQUIRED" in message:
        raise KeyError("PROPERTY_HAS_RELATED_RECORDS") from exc
    raise exc


def list_contracts(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(db, "contracts")


def list_contracts_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    return _page_query(
        db,
        "contracts",
        ["id", "property_id", "tenant", "room", "start_date", "end_date", "monthly_rent", "deposit", "status", "days_left"],
        "id",
        limit,
        offset,
        q,
    )


def get_contract(db: sqlite3.Connection, contract_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
    return _contract_from_row(row)


def create_contract(db: sqlite3.Connection, contract_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if get_contract(db, contract_data["id"]):
                raise KeyError("CONTRACT_ALREADY_EXISTS")
            values = _contract_values(db, contract_data)
            db.execute(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (:id, :property_id, :tenant, :room, :start_date, :end_date, :monthly_rent, :deposit, :status, :days_left)
                """,
                values,
            )
            _audit_if_requested(db, actor, "create", "contract", values["id"])
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    created = get_contract(db, contract_data["id"])
    if not created:
        raise KeyError("CONTRACT_NOT_FOUND")
    return created


def update_pending_contract(db: sqlite3.Connection, contract_id: str, contract_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            existing = get_contract(db, contract_id)
            if not existing:
                raise KeyError("CONTRACT_NOT_FOUND")
            if existing["status"] != "pending":
                raise KeyError("INVALID_CONTRACT_STATUS")
            values = {**_contract_values(db, contract_data), "id": contract_id}
            db.execute(
                """
                UPDATE contracts
                SET property_id = :property_id,
                    tenant = :tenant,
                    room = :room,
                    start_date = :start_date,
                    end_date = :end_date,
                    monthly_rent = :monthly_rent,
                    deposit = :deposit,
                    status = :status,
                    days_left = :days_left
                WHERE id = :id
                """,
                values,
            )
            _audit_if_requested(db, actor, "update", "contract", contract_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    updated = get_contract(db, contract_id)
    if not updated:
        raise KeyError("CONTRACT_NOT_FOUND")
    return updated


def approve_contract(db: sqlite3.Connection, contract_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            contract = get_contract(db, contract_id)
            if not contract:
                raise KeyError("CONTRACT_NOT_FOUND")
            if contract["status"] != "pending":
                raise KeyError("INVALID_CONTRACT_STATUS")
            days_left = _contract_days_left(contract["end_date"])
            db.execute("UPDATE contracts SET status = ?, days_left = ? WHERE id = ?", ("active", days_left, contract_id))
            db.execute(
                """
                UPDATE tenants
                SET lease_end = ?
                WHERE contract_id = ? AND property_id = ? AND name = ?
                """,
                (contract["end_date"], contract_id, contract["property_id"], contract["tenant"]),
            )
            db.execute(
                """
                UPDATE properties
                SET status = 'occupied', tenant = ?, lease_end = ?
                WHERE id = ?
                """,
                (contract["tenant"], contract["end_date"], contract["property_id"]),
            )
            _audit_if_requested(db, actor, "approve", "contract", contract_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    approved = get_contract(db, contract_id)
    if not approved:
        raise KeyError("CONTRACT_NOT_FOUND")
    return approved


def terminate_contract(db: sqlite3.Connection, contract_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            contract = get_contract(db, contract_id)
            if not contract:
                raise KeyError("CONTRACT_NOT_FOUND")
            if contract["status"] not in {"pending", "active", "expiring"}:
                raise KeyError("INVALID_CONTRACT_STATUS")
            db.execute("UPDATE contracts SET status = ?, days_left = 0 WHERE id = ?", ("terminated", contract_id))
            has_effective_contract = db.execute(
                "SELECT 1 FROM contracts WHERE id != ? AND property_id = ? AND status IN ('active', 'expiring', 'pending') LIMIT 1",
                (contract_id, contract["property_id"]),
            ).fetchone()
            has_tenant = db.execute("SELECT 1 FROM tenants WHERE property_id = ? AND status = 'active' LIMIT 1", (contract["property_id"],)).fetchone()
            if not has_effective_contract and not has_tenant:
                db.execute(
                    """
                    UPDATE properties
                    SET status = 'vacant', tenant = NULL, lease_end = NULL
                    WHERE id = ?
                    """,
                    (contract["property_id"],),
                )
            _audit_if_requested(db, actor, "terminate", "contract", contract_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    terminated = get_contract(db, contract_id)
    if not terminated:
        raise KeyError("CONTRACT_NOT_FOUND")
    return terminated


def list_contract_renewals(db: sqlite3.Connection, contract_id: str | None = None) -> list[dict[str, Any]]:
    if contract_id is None:
        return _rows(db, "contract_renewals")
    return [dict(row) for row in db.execute("SELECT * FROM contract_renewals WHERE contract_id = ? ORDER BY created_at, id", (contract_id,)).fetchall()]


def list_move_outs(db: sqlite3.Connection, contract_id: str | None = None) -> list[dict[str, Any]]:
    if contract_id is None:
        return _rows(db, "move_outs")
    return [dict(row) for row in db.execute("SELECT * FROM move_outs WHERE contract_id = ? ORDER BY created_at, id", (contract_id,)).fetchall()]


def list_deposit_settlements(db: sqlite3.Connection, move_out_id: str | None = None) -> list[dict[str, Any]]:
    if move_out_id is None:
        return _rows(db, "deposit_settlements")
    return [dict(row) for row in db.execute("SELECT * FROM deposit_settlements WHERE move_out_id = ? ORDER BY settled_date, id", (move_out_id,)).fetchall()]


def _lifecycle_id(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def renew_contract(db: sqlite3.Connection, contract_id: str, renewal_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            contract = get_contract(db, contract_id)
            if not contract:
                raise KeyError("CONTRACT_NOT_FOUND")
            if contract["status"] not in {"active", "expiring"}:
                raise KeyError("INVALID_CONTRACT_STATUS")
            if date.fromisoformat(renewal_data["new_end_date"]) <= date.fromisoformat(contract["end_date"]):
                raise KeyError("INVALID_CONTRACT_PAYLOAD")
            renewal_id = _lifecycle_id("RENEWAL", f"{contract_id}\0{renewal_data['new_end_date']}")
            values = {
                "id": renewal_id,
                "contract_id": contract_id,
                "property_id": contract["property_id"],
                "tenant": contract["tenant"],
                "room": contract["room"],
                "old_end_date": contract["end_date"],
                "new_end_date": renewal_data["new_end_date"],
                "monthly_rent": renewal_data["monthly_rent"],
                "deposit": renewal_data["deposit"],
                "created_at": date.today().isoformat(),
            }
            db.execute(
                """
                INSERT INTO contract_renewals (id, contract_id, property_id, tenant, room, old_end_date, new_end_date, monthly_rent, deposit, created_at)
                VALUES (:id, :contract_id, :property_id, :tenant, :room, :old_end_date, :new_end_date, :monthly_rent, :deposit, :created_at)
                """,
                values,
            )
            deposit_difference = values["deposit"] - contract["deposit"]
            if deposit_difference != 0:
                db.execute(
                    """
                    INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        renewal_id,
                        values["property_id"],
                        values["created_at"],
                        "续签押金调整",
                        values["room"],
                        values["tenant"],
                        deposit_difference,
                        "待收款" if deposit_difference > 0 else "待退款",
                        "pending",
                        f"自动生成续签押金调整；合同编号={contract_id}",
                        contract_id,
                        None,
                        "renewal",
                    ),
                )
            days_left = _contract_days_left(values["new_end_date"])
            db.execute(
                "UPDATE contracts SET end_date = ?, monthly_rent = ?, deposit = ?, days_left = ? WHERE id = ?",
                (values["new_end_date"], values["monthly_rent"], values["deposit"], days_left, contract_id),
            )
            db.execute("UPDATE tenants SET lease_end = ? WHERE contract_id = ? AND status = 'active'", (values["new_end_date"], contract_id))
            db.execute("UPDATE properties SET lease_end = ? WHERE id = ?", (values["new_end_date"], contract["property_id"]))
            _audit_if_requested(db, actor, "renew", "contract", contract_id)
            if deposit_difference != 0:
                _audit_if_requested(db, actor, "create", "finance_transaction", renewal_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    rows = list_contract_renewals(db, contract_id)
    return rows[-1]


def create_move_out(db: sqlite3.Connection, contract_id: str, move_out_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            contract = get_contract(db, contract_id)
            if not contract:
                raise KeyError("CONTRACT_NOT_FOUND")
            if contract["status"] not in {"active", "expiring"}:
                raise KeyError("INVALID_CONTRACT_STATUS")
            if list_move_outs(db, contract_id):
                raise KeyError("MOVE_OUT_ALREADY_EXISTS")
            move_out_id = _lifecycle_id("MOVEOUT", f"{contract_id}\0{move_out_data['move_out_date']}")
            values = {
                "id": move_out_id,
                "contract_id": contract_id,
                "property_id": contract["property_id"],
                "tenant": contract["tenant"],
                "room": contract["room"],
                "move_out_date": move_out_data["move_out_date"],
                "reason": move_out_data.get("reason") or "",
                "status": "pending_settlement",
                "created_at": date.today().isoformat(),
            }
            db.execute(
                """
                INSERT INTO move_outs (id, contract_id, property_id, tenant, room, move_out_date, reason, status, created_at)
                VALUES (:id, :contract_id, :property_id, :tenant, :room, :move_out_date, :reason, :status, :created_at)
                """,
                values,
            )
            db.execute("UPDATE tenants SET status = 'moved_out', move_out_date = ? WHERE contract_id = ? AND status = 'active'", (values["move_out_date"], contract_id))
            db.execute("UPDATE contracts SET status = 'terminated', days_left = 0 WHERE id = ?", (contract_id,))
            db.execute("UPDATE properties SET status = 'vacant', tenant = NULL, lease_end = NULL WHERE id = ?", (contract["property_id"],))
            _audit_if_requested(db, actor, "move_out", "contract", contract_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    rows = list_move_outs(db, contract_id)
    return rows[-1]


def settle_deposit(db: sqlite3.Connection, move_out_id: str, settlement_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            move_out = db.execute("SELECT * FROM move_outs WHERE id = ?", (move_out_id,)).fetchone()
            if not move_out:
                raise KeyError("MOVE_OUT_NOT_FOUND")
            move_out = dict(move_out)
            if move_out["status"] == "settled" or list_deposit_settlements(db, move_out_id):
                raise KeyError("SETTLEMENT_ALREADY_EXISTS")
            contract = get_contract(db, move_out["contract_id"])
            if not contract:
                raise KeyError("CONTRACT_NOT_FOUND")
            deductions = settlement_data["deductions"]
            if deductions > contract["deposit"] or date.fromisoformat(settlement_data["settled_date"]) < date.fromisoformat(move_out["move_out_date"]):
                raise KeyError("INVALID_SETTLEMENT_PAYLOAD")
            settlement_id = _lifecycle_id("SETTLE", f"{move_out_id}\0{settlement_data['settled_date']}")
            refund_amount = contract["deposit"] - deductions
            transaction_id = settlement_id if refund_amount > 0 else None
            values = {
                "id": settlement_id,
                "move_out_id": move_out_id,
                "contract_id": contract["id"],
                "property_id": contract["property_id"],
                "tenant": contract["tenant"],
                "room": contract["room"],
                "deposit": contract["deposit"],
                "deductions": deductions,
                "rent_deduction": settlement_data.get("rent_deduction", 0),
                "utility_deduction": settlement_data.get("utility_deduction", 0),
                "damage_deduction": settlement_data.get("damage_deduction", 0),
                "cleaning_deduction": settlement_data.get("cleaning_deduction", 0),
                "other_deduction": settlement_data.get("other_deduction", 0),
                "refund_amount": refund_amount,
                "settled_date": settlement_data["settled_date"],
                "status": "settled",
                "method": settlement_data["method"],
                "note": settlement_data["note"],
                "finance_transaction_id": transaction_id,
            }
            db.execute(
                """
                INSERT INTO deposit_settlements (id, move_out_id, contract_id, property_id, tenant, room, deposit, deductions, rent_deduction, utility_deduction, damage_deduction, cleaning_deduction, other_deduction, refund_amount, settled_date, status, method, note, finance_transaction_id)
                VALUES (:id, :move_out_id, :contract_id, :property_id, :tenant, :room, :deposit, :deductions, :rent_deduction, :utility_deduction, :damage_deduction, :cleaning_deduction, :other_deduction, :refund_amount, :settled_date, :status, :method, :note, :finance_transaction_id)
                """,
                values,
            )
            db.execute("UPDATE move_outs SET status = 'settled' WHERE id = ? AND status != 'settled'", (move_out_id,))
            _audit_if_requested(db, actor, "settle", "move_out", move_out_id)
            _audit_if_requested(db, actor, "create", "deposit_settlement", settlement_id)
            if transaction_id is not None:
                _audit_if_requested(db, actor, "create", "finance_transaction", transaction_id)
    except sqlite3.IntegrityError as exc:
        _raise_contract_integrity_error(exc)
    rows = list_deposit_settlements(db, move_out_id)
    return rows[-1]


def list_maintenance_orders(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(db, "maintenance_orders")


def list_maintenance_orders_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    return _page_query(
        db,
        "maintenance_orders",
        ["id", "property_id", "title", "room", "tenant", "category", "priority", "status", "assignee", "created_at", "due_at"],
        "created_at DESC, id DESC",
        limit,
        offset,
        q,
    )


def get_maintenance_order(db: sqlite3.Connection, order_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM maintenance_orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def _maintenance_values(db: sqlite3.Connection, order_data: dict[str, Any]) -> dict[str, Any]:
    property_item = get_property(db, order_data["property_id"])
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    created_at = date.today().isoformat()
    if date.fromisoformat(order_data["due_at"]) < date.fromisoformat(created_at):
        raise KeyError("INVALID_MAINTENANCE_PAYLOAD")
    return {
        **order_data,
        "room": _property_room_key(property_item),
        "status": "open",
        "assignee": "未分配",
        "created_at": created_at,
    }


def _raise_maintenance_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    if "maintenance_orders.id" in message:
        raise KeyError("MAINTENANCE_ORDER_ALREADY_EXISTS") from exc
    if "RELATED_PROPERTY_REQUIRED" in message or "FOREIGN KEY" in message.upper():
        raise KeyError("PROPERTY_NOT_FOUND") from exc
    if "INVALID_MAINTENANCE_STATUS" in message:
        raise KeyError("INVALID_MAINTENANCE_STATUS") from exc
    if "INVALID_MAINTENANCE_PAYLOAD" in message:
        raise KeyError("INVALID_MAINTENANCE_PAYLOAD") from exc
    if "MAINTENANCE_ORDER_DELETE_FORBIDDEN" in message:
        raise KeyError("MAINTENANCE_ORDER_DELETE_FORBIDDEN") from exc
    raise exc


def create_maintenance_order(db: sqlite3.Connection, order_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if get_maintenance_order(db, order_data["id"]):
                raise KeyError("MAINTENANCE_ORDER_ALREADY_EXISTS")
            values = _maintenance_values(db, order_data)
            db.execute(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (:id, :property_id, :title, :room, :tenant, :category, :priority, :status, :assignee, :created_at, :due_at)
                """,
                values,
            )
            _audit_if_requested(db, actor, "create", "maintenance_order", values["id"])
    except sqlite3.IntegrityError as exc:
        _raise_maintenance_integrity_error(exc)
    created = get_maintenance_order(db, order_data["id"])
    if not created:
        raise KeyError("MAINTENANCE_ORDER_NOT_FOUND")
    return created


def assign_maintenance_order(db: sqlite3.Connection, order_id: str, assignee: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            order = get_maintenance_order(db, order_id)
            if not order:
                raise KeyError("MAINTENANCE_ORDER_NOT_FOUND")
            if order["status"] != "open":
                raise KeyError("INVALID_MAINTENANCE_STATUS")
            db.execute("UPDATE maintenance_orders SET status = ?, assignee = ? WHERE id = ?", ("in_progress", assignee, order_id))
            _audit_if_requested(db, actor, "assign", "maintenance_order", order_id)
    except sqlite3.IntegrityError as exc:
        _raise_maintenance_integrity_error(exc)
    assigned = get_maintenance_order(db, order_id)
    if not assigned:
        raise KeyError("MAINTENANCE_ORDER_NOT_FOUND")
    return assigned


def resolve_maintenance_order(db: sqlite3.Connection, order_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            order = get_maintenance_order(db, order_id)
            if not order:
                raise KeyError("MAINTENANCE_ORDER_NOT_FOUND")
            if order["status"] != "in_progress":
                raise KeyError("INVALID_MAINTENANCE_STATUS")
            db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("resolved", order_id))
            _audit_if_requested(db, actor, "resolve", "maintenance_order", order_id)
    except sqlite3.IntegrityError as exc:
        _raise_maintenance_integrity_error(exc)
    resolved = get_maintenance_order(db, order_id)
    if not resolved:
        raise KeyError("MAINTENANCE_ORDER_NOT_FOUND")
    return resolved


def _raise_finance_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    if "RESERVED_FINANCE_TRANSACTION_ID" in message:
        raise KeyError("RESERVED_FINANCE_TRANSACTION_ID") from exc
    if "INVALID_FINANCE_PAYLOAD" in message or "FINANCE_TRANSACTION_DELETE_FORBIDDEN" in message:
        raise KeyError("INVALID_FINANCE_PAYLOAD") from exc
    if "RELATED_PROPERTY_REQUIRED" in message:
        raise KeyError("PROPERTY_NOT_FOUND") from exc
    if "finance_transactions.id" in message:
        raise KeyError("FINANCE_TRANSACTION_ALREADY_EXISTS") from exc
    raise exc


def _raise_reconciliation_integrity_error(exc: sqlite3.IntegrityError) -> None:
    message = str(exc)
    if "reconciliation_records.id" in message:
        raise KeyError("RECONCILIATION_RECORD_ALREADY_EXISTS") from exc
    if "INVALID_RECONCILIATION_PAYLOAD" in message:
        raise KeyError("INVALID_RECONCILIATION_PAYLOAD") from exc
    if "RECONCILIATION_FLOW_ALREADY_EXISTS" in message:
        raise KeyError("RECONCILIATION_FLOW_ALREADY_EXISTS") from exc
    if "RECONCILIATION_MATCHED_IMMUTABLE" in message:
        raise KeyError("INVALID_RECONCILIATION_PAYLOAD") from exc
    raise exc


def _csv_cell(value: Any) -> Any:
    if isinstance(value, str):
        first_content = value.lstrip()[:1]
        if (value and ord(value[0]) < 32) or first_content in {"=", "+", "-", "@"}:
            return f"'{value}"
    return value


def _csv_content(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_cell(row.get(field, "")) for field in fieldnames})
    return output.getvalue()


def list_transactions(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(db, "finance_transactions")


def list_transactions_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    return _page_query(
        db,
        "finance_transactions",
        ["id", "property_id", "date", "type", "room", "tenant", "amount", "method", "status", "note", "contract_id", "settlement_id", "lifecycle_type"],
        "date DESC, id DESC",
        limit,
        offset,
        q,
    )


def _month_bounds(month: str) -> tuple[date, date]:
    year_text, month_text = month.split("-", 1)
    year = int(year_text)
    month_number = int(month_text)
    last_day = calendar.monthrange(year, month_number)[1]
    return date(year, month_number, 1), date(year, month_number, last_day)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month_number = month_index % 12 + 1
    return date(year, month_number, min(value.day, calendar.monthrange(year, month_number)[1]))


def _clamped_month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _rent_bill_id(contract_id: str, month: str) -> str:
    digest = hashlib.sha256(f"{contract_id}\0{month}".encode("utf-8")).hexdigest()[:16].upper()
    return f"RENT-{month.replace('-', '')}-{digest}"


def _rent_bill_note(contract_id: str, month: str) -> str:
    return f"自动生成租金账单；合同编号={contract_id}；账期={month}"


def _is_generated_rent_bill(transaction: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(transaction[field] == expected[field] for field in ("id", "property_id", "date", "type", "room", "tenant", "amount", "method", "note", "contract_id", "settlement_id", "lifecycle_type"))


def get_transaction(db: sqlite3.Connection, transaction_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM finance_transactions WHERE id = ?", (transaction_id,)).fetchone()
    return dict(row) if row else None


def create_transaction(db: sqlite3.Connection, transaction_data: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    property_item = get_property(db, transaction_data["property_id"])
    if not property_item:
        raise KeyError("PROPERTY_NOT_FOUND")
    if transaction_data["id"].startswith(("RENT-", "SETTLE-", "RENEWAL-")):
        raise KeyError("RESERVED_FINANCE_TRANSACTION_ID")
    if {"contract_id", "settlement_id", "lifecycle_type"} & transaction_data.keys():
        raise KeyError("INVALID_FINANCE_PAYLOAD")
    if get_transaction(db, transaction_data["id"]):
        raise KeyError("FINANCE_TRANSACTION_ALREADY_EXISTS")

    values = {
        **transaction_data,
        "room": _property_room_key(property_item),
        "tenant": transaction_data.get("tenant") or property_item.get("tenant") or "-",
        "note": transaction_data.get("note") or "",
        "contract_id": transaction_data.get("contract_id"),
        "settlement_id": transaction_data.get("settlement_id"),
        "lifecycle_type": transaction_data.get("lifecycle_type"),
    }
    try:
        with db:
            db.execute(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
                VALUES (:id, :property_id, :date, :type, :room, :tenant, :amount, :method, :status, :note, :contract_id, :settlement_id, :lifecycle_type)
                """,
                values,
            )
            _audit_if_requested(db, actor, "create", "finance_transaction", values["id"])
    except sqlite3.IntegrityError as exc:
        _raise_finance_integrity_error(exc)
    created = get_transaction(db, transaction_data["id"])
    if not created:
        raise KeyError("FINANCE_TRANSACTION_NOT_FOUND")
    return created


def confirm_transaction(db: sqlite3.Connection, transaction_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            transaction = get_transaction(db, transaction_id)
            if not transaction:
                raise KeyError("FINANCE_TRANSACTION_NOT_FOUND")
            if transaction["status"] not in {"pending", "overdue"}:
                raise KeyError("INVALID_FINANCE_STATUS")
            db.execute("UPDATE finance_transactions SET status = ? WHERE id = ?", ("paid", transaction_id))
            _audit_if_requested(db, actor, "confirm", "finance_transaction", transaction_id)
    except sqlite3.IntegrityError as exc:
        _raise_finance_integrity_error(exc)
    confirmed = get_transaction(db, transaction_id)
    if not confirmed:
        raise KeyError("FINANCE_TRANSACTION_NOT_FOUND")
    return confirmed


def generate_rent_bills(db: sqlite3.Connection, month: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    month_start, month_end = _month_bounds(month)
    today = date.today()
    created_ids: list[str] = []
    skipped = 0
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            contracts = [
                contract
                for contract in list_contracts(db)
                if contract["status"] in {"active", "expiring"}
                and date.fromisoformat(contract["start_date"]) <= month_end
                and date.fromisoformat(contract["end_date"]) >= month_start
            ]
            for contract in contracts:
                bill_id = _rent_bill_id(contract["id"], month)
                due_date = _clamped_month_day(month_start.year, month_start.month, date.fromisoformat(contract["start_date"]).day)
                values = {
                    "id": bill_id,
                    "property_id": contract["property_id"],
                    "date": due_date.isoformat(),
                    "type": "租金账单",
                    "room": contract["room"],
                    "tenant": contract["tenant"],
                    "amount": contract["monthly_rent"],
                    "method": "待收款",
                    "status": "overdue" if due_date < today else "pending",
                    "note": _rent_bill_note(contract["id"], month),
                    "contract_id": contract["id"],
                    "settlement_id": None,
                    "lifecycle_type": "rent",
                }
                existing = get_transaction(db, bill_id)
                if existing:
                    if not _is_generated_rent_bill(existing, values):
                        raise KeyError("FINANCE_TRANSACTION_ALREADY_EXISTS")
                    skipped += 1
                    continue
                db.execute(
                    """
                    INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
                    VALUES (:id, :property_id, :date, :type, :room, :tenant, :amount, :method, :status, :note, :contract_id, :settlement_id, :lifecycle_type)
                    """,
                    values,
                )
                created_ids.append(bill_id)
            _audit_if_requested(db, actor, "generate", "rent_bill", month)
    except sqlite3.IntegrityError as exc:
        _raise_finance_integrity_error(exc)
    transactions = [transaction for transaction_id in created_ids if (transaction := get_transaction(db, transaction_id))]
    return {"month": month, "created": len(transactions), "skipped": skipped, "transactions": transactions}


def export_transactions_csv(db: sqlite3.Connection) -> str:
    return _csv_content(list_transactions(db), ["id", "property_id", "date", "type", "room", "tenant", "amount", "method", "status", "note", "contract_id", "settlement_id", "lifecycle_type"])


def export_deposit_settlements_csv(db: sqlite3.Connection) -> str:
    return _csv_content(list_deposit_settlements(db), ["id", "move_out_id", "contract_id", "property_id", "tenant", "room", "deposit", "deductions", "rent_deduction", "utility_deduction", "damage_deduction", "cleaning_deduction", "other_deduction", "refund_amount", "settled_date", "status", "method", "note", "finance_transaction_id"])


def list_reconciliation_records(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(db, "reconciliation_records")


def list_reconciliation_records_page(db: sqlite3.Connection, limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
    return _page_query(
        db,
        "reconciliation_records",
        ["id", "date", "bank_flow_id", "system_flow_id", "payer", "amount", "channel", "status", "difference"],
        "date DESC, id DESC",
        limit,
        offset,
        q,
    )


def get_reconciliation_record(db: sqlite3.Connection, record_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM reconciliation_records WHERE id = ?", (record_id,)).fetchone()
    return dict(row) if row else None


def _reconciliation_flow_exists(db: sqlite3.Connection, field: str, value: str, statuses: tuple[str, ...] | None = None) -> bool:
    if field not in {"bank_flow_id", "system_flow_id"}:
        raise ValueError("invalid reconciliation field")
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        row = db.execute(f"SELECT 1 FROM reconciliation_records WHERE {field} = ? AND status IN ({placeholders}) LIMIT 1", (value, *statuses)).fetchone()
    else:
        row = db.execute(f"SELECT 1 FROM reconciliation_records WHERE {field} = ? LIMIT 1", (value,)).fetchone()
    return row is not None


def _reconciliation_values(db: sqlite3.Connection, record_data: dict[str, Any]) -> dict[str, Any]:
    transaction = get_transaction(db, record_data["system_flow_id"])
    if not transaction:
        return {**record_data, "status": "pending", "difference": 0}
    difference = record_data["amount"] - transaction["amount"]
    if difference != 0:
        return {**record_data, "status": "exception", "difference": difference}
    if transaction["status"] != "paid" or transaction["tenant"] != record_data["payer"] or transaction["date"] != record_data["date"] or transaction["method"] != record_data["channel"]:
        return {**record_data, "status": "exception", "difference": 0}
    return {**record_data, "status": "matched", "difference": 0}


def import_reconciliation_records(db: sqlite3.Connection, records: list[dict[str, Any]], actor: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    imported: list[dict[str, Any]] = []
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            for record in records:
                if get_reconciliation_record(db, record["id"]):
                    raise KeyError("RECONCILIATION_RECORD_ALREADY_EXISTS")
                if _reconciliation_flow_exists(db, "bank_flow_id", record["bank_flow_id"]):
                    raise KeyError("RECONCILIATION_FLOW_ALREADY_EXISTS")
                values = _reconciliation_values(db, record)
                if values["status"] != "pending" and _reconciliation_flow_exists(db, "system_flow_id", record["system_flow_id"], ("matched", "exception")):
                    raise KeyError("RECONCILIATION_FLOW_ALREADY_EXISTS")
                db.execute(
                    """
                    INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
                    VALUES (:id, :date, :bank_flow_id, :system_flow_id, :payer, :amount, :channel, :status, :difference)
                    """,
                    values,
                )
                if values["status"] == "matched":
                    db.execute("UPDATE finance_transactions SET status = ? WHERE id = ?", ("reconciled", values["system_flow_id"]))
                imported.append(values)
            _audit_if_requested(db, actor, "import", "reconciliation", str(len(imported)))
    except sqlite3.IntegrityError as exc:
        _raise_reconciliation_integrity_error(exc)
    return imported


def retry_reconciliation_record(db: sqlite3.Connection, record_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            record = get_reconciliation_record(db, record_id)
            if not record:
                raise KeyError("RECONCILIATION_RECORD_NOT_FOUND")
            if record["status"] in {"matched", "reviewed"}:
                raise KeyError("INVALID_RECONCILIATION_STATUS")
            values = _reconciliation_values(db, record)
            if values["status"] != "pending":
                duplicate = db.execute(
                    "SELECT 1 FROM reconciliation_records WHERE id != ? AND system_flow_id = ? AND status IN ('matched', 'exception') LIMIT 1",
                    (record_id, values["system_flow_id"]),
                ).fetchone()
                if duplicate:
                    raise KeyError("RECONCILIATION_FLOW_ALREADY_EXISTS")
            db.execute(
                "UPDATE reconciliation_records SET status = ?, difference = ? WHERE id = ?",
                (values["status"], values["difference"], record_id),
            )
            if values["status"] == "matched":
                db.execute("UPDATE finance_transactions SET status = ? WHERE id = ?", ("reconciled", values["system_flow_id"]))
            _audit_if_requested(db, actor, "retry", "reconciliation", record_id)
    except sqlite3.IntegrityError as exc:
        _raise_reconciliation_integrity_error(exc)
    retried = get_reconciliation_record(db, record_id)
    if not retried:
        raise KeyError("RECONCILIATION_RECORD_NOT_FOUND")
    return retried


def resolve_reconciliation_record(db: sqlite3.Connection, record_id: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            record = get_reconciliation_record(db, record_id)
            if not record:
                raise KeyError("RECONCILIATION_RECORD_NOT_FOUND")
            if record["status"] != "exception":
                raise KeyError("INVALID_RECONCILIATION_STATUS")
            db.execute("UPDATE reconciliation_records SET status = ? WHERE id = ?", ("reviewed", record_id))
            _audit_if_requested(db, actor, "resolve", "reconciliation", record_id)
    except sqlite3.IntegrityError as exc:
        _raise_reconciliation_integrity_error(exc)
    resolved = get_reconciliation_record(db, record_id)
    if not resolved:
        raise KeyError("RECONCILIATION_RECORD_NOT_FOUND")
    return resolved


def export_reconciliation_csv(db: sqlite3.Connection) -> str:
    return _csv_content(list_reconciliation_records(db), ["id", "date", "bank_flow_id", "system_flow_id", "payer", "amount", "channel", "status", "difference"])


TODO_SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _todo_overdue(item: dict[str, Any], today: date) -> bool:
    due_date = _parse_iso_date(item.get("due_date"))
    return due_date is not None and due_date < today


def _todo_sort_key(item: dict[str, Any]) -> tuple[int, date, str, str]:
    due_date = _parse_iso_date(item.get("due_date")) or date.max
    return (TODO_SEVERITY_ORDER[item["severity"]], due_date, item["source"], item["source_id"])


def list_todos(
    db: sqlite3.Connection,
    allowed_sources: set[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
    q: str | None = None,
    source: str | None = None,
    severity_filter: str | None = None,
) -> dict[str, Any]:
    today = date.today()
    items: list[dict[str, Any]] = []
    sources = allowed_sources if allowed_sources is not None else {"contracts", "maintenance", "finance", "reconciliation"}
    if source and source in sources:
        sources = {source}
    elif source:
        sources = set()

    if "maintenance" in sources:
        for order in list_maintenance_orders(db):
            if order["status"] == "resolved":
                continue
            due_date = _parse_iso_date(order["due_at"])
            if order["priority"] == "urgent" or (due_date is not None and due_date < today):
                severity = "danger"
            elif order["priority"] == "high" or due_date == today:
                severity = "warning"
            else:
                severity = "info"
            items.append(
                {
                    "id": f"maintenance:{order['id']}",
                    "source": "maintenance",
                    "source_id": order["id"],
                    "title": f"维修工单待处理：{order['title']}",
                    "description": f"{order['room']} · {order['tenant']} · {order['category']}",
                    "due_date": order["due_at"],
                    "severity": severity,
                    "status": order["status"],
                    "assignee": order["assignee"],
                    "related_room": order["room"],
                    "related_person": order["tenant"],
                }
            )

    if "contracts" in sources:
        for contract in list_contracts(db):
            end_date = _parse_iso_date(contract["end_date"])
            days_left = (end_date - today).days if end_date is not None else contract["days_left"]
            should_include = contract["status"] == "pending" or contract["status"] == "expiring" or (contract["status"] == "active" and days_left <= 30)
            if not should_include:
                continue
            severity = "danger" if days_left <= 7 else "warning"
            title = f"合同待审批：{contract['tenant']}" if contract["status"] == "pending" else f"合同即将到期：{contract['tenant']}"
            items.append(
                {
                    "id": f"contracts:{contract['id']}",
                    "source": "contracts",
                    "source_id": contract["id"],
                    "title": title,
                    "description": f"{contract['room']} · {contract['start_date']} 至 {contract['end_date']}",
                    "due_date": contract["end_date"],
                    "severity": severity,
                    "status": contract["status"],
                    "assignee": None,
                    "related_room": contract["room"],
                    "related_person": contract["tenant"],
                }
            )

    if "contracts" in sources:
        for move_out in list_move_outs(db):
            if move_out["status"] != "pending_settlement":
                continue
            items.append(
                {
                    "id": f"contracts:move_out:{move_out['id']}",
                    "source": "contracts",
                    "source_id": f"move_out:{move_out['id']}",
                    "title": f"退租待结算：{move_out['tenant']}",
                    "description": f"{move_out['room']} · 退租日期 {move_out['move_out_date']}",
                    "due_date": move_out["move_out_date"],
                    "severity": "warning",
                    "status": move_out["status"],
                    "assignee": None,
                    "related_room": move_out["room"],
                    "related_person": move_out["tenant"],
                }
            )

    if "finance" in sources:
        for transaction in list_transactions(db):
            if transaction["status"] not in {"pending", "overdue"}:
                continue
            severity = "danger" if transaction["status"] == "overdue" else "warning"
            title = f"逾期账单：{transaction['type']}" if transaction["status"] == "overdue" else f"账单待确认：{transaction['type']}"
            items.append(
                {
                    "id": f"finance:{transaction['id']}",
                    "source": "finance",
                    "source_id": transaction["id"],
                    "title": title,
                    "description": f"{transaction['room']} · {transaction['tenant']} · {transaction['amount']}",
                    "due_date": transaction["date"],
                    "severity": severity,
                    "status": transaction["status"],
                    "assignee": None,
                    "related_room": transaction["room"],
                    "related_person": transaction["tenant"],
                }
            )

    if "reconciliation" in sources:
        for record in list_reconciliation_records(db):
            if record["status"] not in {"pending", "exception"}:
                continue
            severity = "danger" if record["status"] == "exception" else "warning"
            title = f"对账异常：{record['bank_flow_id']}" if record["status"] == "exception" else f"流水待匹配：{record['bank_flow_id']}"
            items.append(
                {
                    "id": f"reconciliation:{record['id']}",
                    "source": "reconciliation",
                    "source_id": record["id"],
                    "title": title,
                    "description": f"{record['payer']} · {record['channel']} · 差额 {record['difference']}",
                    "due_date": record["date"],
                    "severity": severity,
                    "status": record["status"],
                    "assignee": None,
                    "related_room": None,
                    "related_person": record["payer"],
                }
            )

    items.sort(key=_todo_sort_key)
    if severity_filter:
        items = [item for item in items if item["severity"] == severity_filter]
    items = _filter_items(items, q, ["id", "source", "source_id", "title", "description", "due_date", "severity", "status", "assignee", "related_room", "related_person"])
    total = len(items)
    paged_items = items[offset : offset + limit] if limit is not None else items
    return {
        "total": total,
        "urgent": sum(1 for item in items if item["severity"] == "danger"),
        "overdue": sum(1 for item in items if _todo_overdue(item, today)),
        "items": paged_items,
        "limit": limit,
        "offset": offset,
    }


def export_dashboard_csv(db: sqlite3.Connection, allowed_sources: set[str] | None = None) -> str:
    summary = get_dashboard_summary(db, allowed_sources)
    rows = [
        {"section": "metric", "label": metric["label"], "value": metric["value"], "change": metric["change"], "tone": metric["tone"]}
        for metric in summary["metrics"]
    ]
    rows.extend(
        [
            {"section": "summary", "label": "occupancy_rate", "value": summary["occupancy_rate"], "change": "", "tone": ""},
            {"section": "summary", "label": "monthly_income", "value": summary["monthly_income"], "change": "", "tone": ""},
            {"section": "summary", "label": "pending_tasks", "value": summary["pending_tasks"], "change": "", "tone": ""},
            {"section": "summary", "label": "expiring_contracts", "value": summary["expiring_contracts"], "change": "", "tone": ""},
        ]
    )
    return _csv_content(rows, ["section", "label", "value", "change", "tone"])


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _month_label(value: date) -> str:
    return f"{value.month:02d}月"


def _transaction_received_income(transaction: dict[str, Any]) -> bool:
    return transaction["amount"] > 0 and transaction["status"] in {"paid", "reconciled"}


def _current_month_income(transactions: list[dict[str, Any]], today: date) -> int:
    current_month = _month_key(today)
    return sum(transaction["amount"] for transaction in transactions if _transaction_received_income(transaction) and transaction["date"].startswith(current_month))


def _previous_month_income(transactions: list[dict[str, Any]], today: date) -> int:
    previous_month = _month_key(_add_months(today.replace(day=1), -1))
    return sum(transaction["amount"] for transaction in transactions if _transaction_received_income(transaction) and transaction["date"].startswith(previous_month))


def _income_change(current: int, previous: int) -> str:
    if previous == 0:
        return "较上月新增收入" if current > 0 else "较上月持平"
    percentage = round((current - previous) / previous * 100)
    return f"较上月{'+' if percentage >= 0 else ''}{percentage}%"


def _dashboard_income_trend(transactions: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    first_month = _add_months(today.replace(day=1), -5)
    months = [_add_months(first_month, offset) for offset in range(6)]
    return [
        {
            "month": _month_label(month),
            "income": sum(transaction["amount"] for transaction in transactions if _transaction_received_income(transaction) and transaction["date"].startswith(_month_key(month))),
        }
        for month in months
    ]


def _expiring_contract_count(contracts: list[dict[str, Any]], today: date) -> int:
    count = 0
    for contract in contracts:
        end_date = _parse_iso_date(contract["end_date"])
        days_left = (end_date - today).days if end_date else contract["days_left"]
        if contract["status"] == "expiring" or (contract["status"] == "active" and days_left <= 30):
            count += 1
    return count


def _maintenance_priority_rank(order: dict[str, Any], today: date) -> tuple[int, int, date, str]:
    due_date = _parse_iso_date(order["due_at"]) or date.max
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}[order["priority"]]
    overdue_rank = 0 if due_date < today else 1
    return (overdue_rank, priority_rank, due_date, order["id"])


def get_dashboard_summary(db: sqlite3.Connection, allowed_sources: set[str] | None = None) -> dict[str, Any]:
    today = date.today()
    sources = allowed_sources if allowed_sources is not None else {"properties", "contracts", "maintenance", "finance", "reconciliation"}
    properties = list_properties(db) if "properties" in sources else []
    contracts = list_contracts(db) if "contracts" in sources else []
    orders = list_maintenance_orders(db) if "maintenance" in sources else []
    transactions = list_transactions(db) if "finance" in sources else []
    todo_summary = list_todos(db, sources - {"properties"})

    occupied = sum(1 for item in properties if item["status"] == "occupied")
    total = len(properties)
    occupancy_rate = round(occupied / (total or 1) * 100)
    monthly_income = _current_month_income(transactions, today)
    previous_income = _previous_month_income(transactions, today)
    pending_tasks = todo_summary["total"]
    expiring_contracts = _expiring_contract_count(contracts, today)
    recent_contracts = sorted(contracts, key=lambda contract: (contract["start_date"], contract["id"]), reverse=True)[:4]
    urgent_work_orders = sorted((order for order in orders if order["status"] != "resolved"), key=lambda order: _maintenance_priority_rank(order, today))[:3]

    return {
        "metrics": [
            {"label": "房源总数", "value": str(total), "change": f"已出租 {occupied} 套", "tone": "primary"},
            {"label": "出租率", "value": f"{occupancy_rate}%", "change": f"空置 {sum(1 for item in properties if item['status'] == 'vacant')} 套", "tone": "success"},
            {"label": "本月收入", "value": f"¥{monthly_income:,}", "change": _income_change(monthly_income, previous_income), "tone": "warning"},
            {"label": "待办事项", "value": str(pending_tasks), "change": f"紧急 {todo_summary['urgent']} 项", "tone": "danger" if todo_summary["urgent"] else "primary"},
        ],
        "occupancy_rate": occupancy_rate,
        "monthly_income": monthly_income,
        "pending_tasks": pending_tasks,
        "expiring_contracts": expiring_contracts,
        "recent_contracts": recent_contracts,
        "urgent_work_orders": urgent_work_orders,
        "income_trend": _dashboard_income_trend(transactions, today),
    }
