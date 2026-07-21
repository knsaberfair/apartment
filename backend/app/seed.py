from datetime import datetime, timezone
import json
import sqlite3

from app.config import ENABLE_DEMO_SEED
from app.mock_data import CONTRACTS, MAINTENANCE_ORDERS, PROPERTIES, RECONCILIATION, TENANTS, TRANSACTIONS
from app.rbac import BUILT_IN_PERMISSION_RESOURCES, ROLE_LABELS, ROLE_PERMISSIONS
from app.security import hash_password

def _room_key(building: str, room: str) -> str:
    building_code = building.replace(" 栋", "").replace("栋", "").strip()
    return f"{building_code}-{room}"


def _property_id_by_room() -> dict[str, str]:
    return {_room_key(item["building"], item["room"]): item["id"] for item in PROPERTIES}


DEMO_USERS = [
    ("demo-super-admin", "admin", "系统管理员", "admin123", "super_admin"),
    ("demo-manager", "manager", "运营经理", "manager123", "manager"),
    ("demo-leasing", "leasing", "租务专员", "leasing123", "leasing_agent"),
    ("demo-maintenance", "maintenance", "维修人员", "maintenance123", "maintenance_staff"),
    ("demo-finance", "finance", "财务人员", "finance123", "finance_staff"),
    ("demo-viewer", "viewer", "只读访客", "viewer123", "viewer"),
]


def _table_empty(db: sqlite3.Connection, table: str) -> bool:
    return db.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] == 0


def seed_if_empty(db: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db:
        for key, label in ROLE_LABELS.items():
            db.execute(
                "INSERT OR IGNORE INTO roles (key, label, built_in) VALUES (?, ?, 1)",
                (key, label),
            )

        for resource in BUILT_IN_PERMISSION_RESOURCES.values():
            db.execute(
                """
                INSERT OR IGNORE INTO permission_resources
                (key, label, description, group_key, group_label, type, route, menu_label, menu_hint, sort, built_in)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    resource["key"],
                    resource["label"],
                    resource["description"],
                    resource["group"],
                    resource["group_label"],
                    resource["type"],
                    resource.get("route"),
                    resource.get("menu_label"),
                    resource.get("menu_hint"),
                    resource.get("sort", 1000),
                ),
            )

        for role, permissions in ROLE_PERMISSIONS.items():
            db.executemany(
                "INSERT OR IGNORE INTO role_permissions (role_key, permission_key) VALUES (?, ?)",
                [(role, permission) for permission in sorted(permissions)],
            )

        if ENABLE_DEMO_SEED and _table_empty(db, "users"):
            db.executemany(
                """
                INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                [(user_id, username, display_name, hash_password(password), role, now) for user_id, username, display_name, password, role in DEMO_USERS],
            )

        property_ids = _property_id_by_room()

        if ENABLE_DEMO_SEED and _table_empty(db, "properties"):
            relationship_rooms = {_room_key(item["building"], item["room"]) for item in PROPERTIES if item["status"] in {"occupied", "reserved"}}
            db.executemany(
                """
                INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
                VALUES (:id, :building, :room, :room_key, :layout, :area, :rent, :status, :tenant, :lease_end, :tags_json)
                """,
                [
                    {
                        **item,
                        "room_key": _room_key(item["building"], item["room"]),
                        "status": "vacant" if _room_key(item["building"], item["room"]) in relationship_rooms else item["status"],
                        "tenant": None if _room_key(item["building"], item["room"]) in relationship_rooms else item["tenant"],
                        "lease_end": None if _room_key(item["building"], item["room"]) in relationship_rooms else item["lease_end"],
                        "tags_json": json.dumps(item["tags"], ensure_ascii=False),
                    }
                    for item in PROPERTIES
                ],
            )

        if ENABLE_DEMO_SEED and _table_empty(db, "tenants"):
            db.executemany(
                """
                INSERT INTO tenants (id, property_id, name, phone, room, contract_id, payment_status, move_in_date, lease_end, balance, status, move_out_date)
                VALUES (:id, :property_id, :name, :phone, :room, :contract_id, :payment_status, :move_in_date, :lease_end, :balance, :status, :move_out_date)
                """,
                [{**item, "property_id": property_ids.get(item["room"]), "status": "active", "move_out_date": None} for item in TENANTS],
            )

        if ENABLE_DEMO_SEED and _table_empty(db, "contracts"):
            seeded_contracts = [{**item, "property_id": property_ids.get(item["room"])} for item in CONTRACTS]
            db.executemany(
                """
                INSERT INTO contracts (id, property_id, tenant, room, start_date, end_date, monthly_rent, deposit, status, days_left)
                VALUES (:id, :property_id, :tenant, :room, :start_date, :end_date, :monthly_rent, :deposit, 'pending', :days_left)
                """,
                seeded_contracts,
            )
            for contract in seeded_contracts:
                if contract["status"] in {"active", "expiring"}:
                    db.execute("UPDATE contracts SET status = ? WHERE id = ?", ("active", contract["id"]))
                elif contract["status"] == "terminated":
                    db.execute("UPDATE contracts SET status = ?, days_left = 0 WHERE id = ?", ("terminated", contract["id"]))

        if ENABLE_DEMO_SEED and _table_empty(db, "maintenance_orders"):
            seeded_orders = [{**item, "property_id": property_ids.get(item["room"])} for item in MAINTENANCE_ORDERS]
            db.executemany(
                """
                INSERT INTO maintenance_orders (id, property_id, title, room, tenant, category, priority, status, assignee, created_at, due_at)
                VALUES (:id, :property_id, :title, :room, :tenant, :category, :priority, 'open', '未分配', :created_at, :due_at)
                """,
                seeded_orders,
            )
            for order in seeded_orders:
                if order["status"] == "in_progress":
                    db.execute("UPDATE maintenance_orders SET status = ?, assignee = ? WHERE id = ?", ("in_progress", order["assignee"], order["id"]))
                elif order["status"] == "resolved":
                    db.execute("UPDATE maintenance_orders SET status = ?, assignee = ? WHERE id = ?", ("in_progress", order["assignee"], order["id"]))
                    db.execute("UPDATE maintenance_orders SET status = ? WHERE id = ?", ("resolved", order["id"]))

        if ENABLE_DEMO_SEED and _table_empty(db, "finance_transactions"):
            db.executemany(
                """
                INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
                VALUES (:id, :property_id, :date, :type, :room, :tenant, :amount, :method, :status, :note, :contract_id, :settlement_id, :lifecycle_type)
                """,
                [{**item, "property_id": property_ids.get(item["room"]), "contract_id": None, "settlement_id": None, "lifecycle_type": None} for item in TRANSACTIONS],
            )

        if ENABLE_DEMO_SEED and _table_empty(db, "reconciliation_records"):
            db.executemany(
                """
                INSERT INTO reconciliation_records (id, date, bank_flow_id, system_flow_id, payer, amount, channel, status, difference)
                VALUES (:id, :date, :bank_flow_id, :system_flow_id, :payer, :amount, :channel, :status, :difference)
                """,
                RECONCILIATION,
            )
            db.executemany(
                """
                UPDATE finance_transactions
                SET status = 'reconciled'
                WHERE id = :system_flow_id
                  AND :status = 'matched'
                """,
                RECONCILIATION,
            )
