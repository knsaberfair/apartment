from collections.abc import Generator
from datetime import date, timedelta
import re
import sqlite3

from app.config import DATABASE_PATH

SCHEMA_VERSION = 6
EXPECTED_SCHEMA = {
    "roles": {"key", "label", "built_in"},
    "permission_resources": {"key", "label", "description", "group_key", "group_label", "type", "route", "menu_label", "menu_hint", "sort", "built_in"},
    "role_permissions": {"role_key", "permission_key"},
    "users": {"id", "username", "display_name", "password_hash", "role_key", "is_active", "created_at"},
    "login_failures": {"id", "key", "created_at"},
    "properties": {"id", "building", "room", "room_key", "layout", "area", "rent", "status", "tenant", "lease_end", "tags_json"},
    "tenants": {"id", "property_id", "name", "phone", "room", "contract_id", "payment_status", "move_in_date", "lease_end", "balance", "status", "move_out_date"},
    "tenant_accounts": {"id", "tenant_id", "openid", "unionid", "display_name", "created_at", "last_login_at"},
    "contracts": {"id", "property_id", "tenant", "room", "start_date", "end_date", "monthly_rent", "deposit", "status", "days_left"},
    "maintenance_orders": {"id", "property_id", "title", "room", "tenant", "category", "priority", "status", "assignee", "created_at", "due_at"},
    "finance_transactions": {"id", "property_id", "date", "type", "room", "tenant", "amount", "method", "status", "note", "contract_id", "settlement_id", "lifecycle_type"},
    "reconciliation_records": {"id", "date", "bank_flow_id", "system_flow_id", "payer", "amount", "channel", "status", "difference"},
    "contract_renewals": {"id", "contract_id", "property_id", "tenant", "room", "old_end_date", "new_end_date", "monthly_rent", "deposit", "created_at"},
    "move_outs": {"id", "contract_id", "property_id", "tenant", "room", "move_out_date", "reason", "status", "created_at"},
    "deposit_settlements": {"id", "move_out_id", "contract_id", "property_id", "tenant", "room", "deposit", "deductions", "rent_deduction", "utility_deduction", "damage_deduction", "cleaning_deduction", "other_deduction", "refund_amount", "settled_date", "status", "method", "note", "finance_transaction_id"},
    "audit_logs": {"id", "actor_id", "actor_name", "actor_role", "action", "resource_type", "resource_id", "created_at"},
}


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def _room_key(building: str, room: str) -> str:
    building_code = building.replace(" 栋", "").replace("栋", "").strip()
    return f"{building_code}-{room}"


def _ensure_property_for_room(db: sqlite3.Connection, room_key: str) -> str:
    existing = db.execute("SELECT id FROM properties WHERE room_key = ?", (room_key,)).fetchone()
    if existing:
        return existing["id"]

    building_code, _, room = room_key.partition("-")
    if not building_code or not room:
        raise RuntimeError(f"Cannot infer property from room {room_key}")
    property_id = f"P-{room}"
    suffix = 1
    while db.execute("SELECT 1 FROM properties WHERE id = ?", (property_id,)).fetchone():
        suffix += 1
        property_id = f"P-{room}-{suffix}"
    db.execute(
        """
        INSERT INTO properties (id, building, room, room_key, layout, area, rent, status, tenant, lease_end, tags_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (property_id, f"{building_code} 栋", room, room_key, "未配置", 1, 0, "vacant", None, None, "[]"),
    )
    return property_id


def _migrate_to_v2(db: sqlite3.Connection) -> None:
    property_columns = {row["name"] for row in db.execute("PRAGMA table_info(properties)").fetchall()}
    if "room_key" not in property_columns:
        db.execute("ALTER TABLE properties ADD COLUMN room_key TEXT")
        rows = db.execute("SELECT id, building, room FROM properties").fetchall()
        for row in rows:
            db.execute("UPDATE properties SET room_key = ? WHERE id = ?", (_room_key(row["building"], row["room"]), row["id"]))
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_properties_room_key ON properties(room_key)")

    for table in ("tenants", "contracts", "maintenance_orders", "finance_transactions"):
        columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if "property_id" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN property_id TEXT REFERENCES properties(id) ON DELETE RESTRICT")
        rows = db.execute(f"SELECT rowid, room FROM {table} WHERE property_id IS NULL").fetchall()
        for row in rows:
            property_id = _ensure_property_for_room(db, row["room"])
            db.execute(f"UPDATE {table} SET property_id = ? WHERE rowid = ?", (property_id, row["rowid"]))



def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_to_v3(db: sqlite3.Connection) -> None:
    _ensure_column(db, "tenants", "status", "TEXT NOT NULL DEFAULT 'active'")
    _ensure_column(db, "tenants", "move_out_date", "TEXT")
    _ensure_column(db, "finance_transactions", "contract_id", "TEXT")
    _ensure_column(db, "finance_transactions", "settlement_id", "TEXT")
    _ensure_column(db, "finance_transactions", "lifecycle_type", "TEXT")


def _migrate_to_v4(db: sqlite3.Connection) -> None:
    for column in ("rent_deduction", "utility_deduction", "damage_deduction", "cleaning_deduction", "other_deduction"):
        _ensure_column(db, "deposit_settlements", column, "INTEGER NOT NULL DEFAULT 0")
    db.execute(
        """
        UPDATE deposit_settlements
        SET other_deduction = deductions
        WHERE deductions > 0
          AND rent_deduction = 0
          AND utility_deduction = 0
          AND damage_deduction = 0
          AND cleaning_deduction = 0
          AND other_deduction = 0
        """
    )


def _migrate_to_v5(db: sqlite3.Connection) -> None:
    _ensure_column(db, "deposit_settlements", "method", "TEXT NOT NULL DEFAULT '银行转账'")
    _ensure_column(db, "deposit_settlements", "note", "TEXT NOT NULL DEFAULT '退租押金结算'")


def _migrate_to_v6(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_accounts (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            openid TEXT UNIQUE NOT NULL,
            unionid TEXT,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        )
        """
    )
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_accounts_tenant_id ON tenant_accounts(tenant_id)")


def _legacy_maintenance_status(value: str) -> str | None:
    if not isinstance(value, str):
        raise ValueError("maintenance status must be text")
    normalized = value.strip()
    if normalized == "waiting":
        return "open"
    if normalized in {"open", "in_progress", "resolved"}:
        return normalized
    return None


def _strict_iso_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must use YYYY-MM-DD format")
    return date.fromisoformat(value)


def _legacy_maintenance_due_date(value: str, created_at: str, status: str) -> str | None:
    if not isinstance(value, str) or not isinstance(created_at, str):
        raise ValueError("maintenance dates must be text")
    normalized = value.strip()
    base_date = _strict_iso_date(created_at)
    if normalized == "已完成" and status == "resolved":
        return created_at
    month_day_match = re.match(r"^(\d{2})-(\d{2})$", normalized)
    if month_day_match:
        due_date = date.fromisoformat(f"{base_date.year}-{normalized}")
        if due_date < base_date:
            due_date = date.fromisoformat(f"{base_date.year + 1}-{normalized}")
        return due_date.isoformat()
    try:
        due_date = date.fromisoformat(normalized)
    except ValueError:
        match = re.match(r"^(今日|今天|明日|明天|后天)(?:\s+\d{1,2}:\d{2})?$", normalized)
        if not match:
            return None
        offset = {"今日": 0, "今天": 0, "明日": 1, "明天": 1, "后天": 2}[match.group(1)]
        due_date = base_date + timedelta(days=offset)
        return due_date.isoformat()

    if due_date < base_date:
        raise ValueError("due_at must be greater than or equal to created_at")
    return due_date.isoformat()


def _normalize_legacy_maintenance_orders(db: sqlite3.Connection) -> None:
    updates: list[tuple[str, str, str]] = []
    invalid_ids: list[str] = []
    rows = db.execute("SELECT id, status, created_at, due_at FROM maintenance_orders").fetchall()
    for row in rows:
        try:
            status = _legacy_maintenance_status(row["status"])
            due_at = _legacy_maintenance_due_date(row["due_at"], row["created_at"], status or "")
        except ValueError:
            status = None
            due_at = None
        if status is None or due_at is None:
            invalid_ids.append(row["id"])
        elif due_at != row["due_at"] or status != row["status"]:
            updates.append((status, due_at, row["id"]))

    if invalid_ids:
        raise RuntimeError(f"Cannot normalize legacy maintenance values for orders: {', '.join(invalid_ids)}")
    if not updates:
        return

    if db.in_transaction:
        db.commit()
    try:
        db.execute("BEGIN IMMEDIATE")
        trigger_names = (
            "maintenance_orders_payload_update_guard",
            "maintenance_orders_status_transition_guard",
            "maintenance_orders_resolved_update_guard",
            "maintenance_orders_non_open_update_guard",
            "maintenance_orders_immutable_update_guard",
        )
        trigger_sql = {
            row["name"]: row["sql"]
            for row in db.execute(
                f"SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND name IN ({', '.join('?' for _ in trigger_names)})",
                trigger_names,
            ).fetchall()
        }
        for trigger in trigger_names:
            db.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        for status, due_at, order_id in updates:
            db.execute("UPDATE maintenance_orders SET status = ?, due_at = ? WHERE id = ?", (status, due_at, order_id))
        for trigger in trigger_names:
            if trigger in trigger_sql:
                db.execute(trigger_sql[trigger])
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise


def _ensure_tenant_property_unique_index(db: sqlite3.Connection) -> None:
    db.execute("DROP INDEX IF EXISTS idx_tenants_property_id")
    db.execute("DROP INDEX IF EXISTS idx_tenants_contract_id")
    duplicate = db.execute(
        """
        SELECT property_id
        FROM tenants
        WHERE property_id IS NOT NULL AND status = 'active'
        GROUP BY property_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate:
        raise RuntimeError(f"Cannot create active tenant property uniqueness index; duplicate active tenant rows exist for property {duplicate['property_id']}")
    duplicate_contract = db.execute(
        """
        SELECT contract_id
        FROM tenants
        WHERE status = 'active'
        GROUP BY contract_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate_contract:
        raise RuntimeError(f"Cannot create active tenant contract uniqueness index; duplicate active tenant rows exist for contract {duplicate_contract['contract_id']}")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_active_property_id ON tenants(property_id) WHERE status = 'active'")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_active_contract_id ON tenants(contract_id) WHERE status = 'active'")


def _install_integrity_triggers(db: sqlite3.Connection) -> None:
    trigger_names = (
        "properties_room_key_insert_guard",
        "properties_room_key_update_guard",
        "properties_payload_insert_guard",
        "properties_payload_update_guard",
        "properties_relationship_insert_guard",
        "properties_relationship_update_guard",
        "properties_occupied_tenant_insert_guard",
        "properties_occupied_tenant_update_guard",
        "properties_tenant_reference_update_guard",
        "properties_room_reference_update_guard",
        "properties_id_reference_update_guard",
        "properties_delete_reference_guard",
        "tenants_payload_insert_guard",
        "tenants_payload_update_guard",
        "tenants_property_id_insert_guard",
        "tenants_property_id_update_guard",
        "tenants_property_available_insert_guard",
        "tenants_property_available_update_guard",
        "tenants_room_insert_guard",
        "tenants_room_update_guard",
        "tenants_property_insert_sync",
        "tenants_property_update_sync",
        "tenants_property_delete_sync",
        "tenants_contract_insert_conflict_guard",
        "tenants_contract_update_conflict_guard",
        "tenants_contract_delete_guard",
        "tenants_activity_delete_guard",
        "tenants_contract_identity_update_guard",
        "tenants_activity_identity_update_guard",
        "contracts_payload_insert_guard",
        "contracts_payload_update_guard",
        "contracts_initial_status_insert_guard",
        "contracts_property_id_insert_guard",
        "contracts_property_id_update_guard",
        "contracts_room_insert_guard",
        "contracts_room_update_guard",
        "contracts_unique_property_insert_guard",
        "contracts_unique_property_update_guard",
        "contracts_tenant_insert_conflict_guard",
        "contracts_tenant_update_conflict_guard",
        "contracts_tenant_termination_guard",
        "contracts_status_transition_guard",
        "contracts_non_pending_update_guard",
        "contracts_delete_guard",
        "contracts_property_insert_sync",
        "contracts_property_update_sync",
        "contracts_property_terminate_sync",
        "maintenance_orders_payload_insert_guard",
        "maintenance_orders_payload_update_guard",
        "maintenance_orders_initial_status_insert_guard",
        "maintenance_orders_status_transition_guard",
        "maintenance_orders_resolved_update_guard",
        "maintenance_orders_non_open_update_guard",
        "maintenance_orders_immutable_update_guard",
        "maintenance_orders_assignee_update_guard",
        "maintenance_orders_delete_guard",
        "maintenance_orders_property_id_insert_guard",
        "maintenance_orders_property_id_update_guard",
        "maintenance_orders_room_insert_guard",
        "maintenance_orders_room_update_guard",
        "finance_transactions_payload_insert_guard",
        "finance_transactions_payload_update_guard",
        "finance_transactions_property_id_insert_guard",
        "finance_transactions_property_id_update_guard",
        "finance_transactions_room_insert_guard",
        "finance_transactions_room_update_guard",
        "finance_transactions_reserved_id_insert_guard",
        "finance_transactions_reserved_id_update_guard",
        "finance_transactions_reconciled_immutable_update_guard",
        "finance_transactions_reconciliation_delete_guard",
        "reconciliation_records_payload_insert_guard",
        "reconciliation_records_payload_update_guard",
        "reconciliation_records_bank_flow_insert_guard",
        "reconciliation_records_bank_flow_update_guard",
        "reconciliation_records_system_flow_insert_guard",
        "reconciliation_records_system_flow_update_guard",
        "reconciliation_records_matched_insert_sync",
        "reconciliation_records_matched_update_sync",
        "reconciliation_records_matched_update_guard",
        "reconciliation_records_matched_delete_guard",
        "contract_renewals_payload_insert_guard",
        "contract_renewals_update_guard",
        "contract_renewals_delete_guard",
        "move_outs_payload_insert_guard",
        "move_outs_update_guard",
        "move_outs_delete_guard",
        "deposit_settlements_payload_insert_guard",
        "deposit_settlements_insert_sync",
        "deposit_settlements_update_guard",
        "deposit_settlements_delete_guard",
        "audit_logs_insert_guard",
        "audit_logs_update_guard",
        "audit_logs_delete_guard",
    )
    drop_statements = "\n".join(f"DROP TRIGGER IF EXISTS {trigger};" for trigger in trigger_names)

    try:
        db.executescript(
            f"""
        BEGIN IMMEDIATE;
        {drop_statements}
        CREATE TRIGGER properties_room_key_insert_guard
        BEFORE INSERT ON properties
        WHEN NEW.room_key IS NULL OR NEW.room_key = '' OR NEW.room_key != replace(replace(NEW.building, ' 栋', ''), '栋', '') || '-' || NEW.room
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_ROOM_KEY');
        END;

        CREATE TRIGGER properties_room_key_update_guard
        BEFORE UPDATE OF building, room, room_key ON properties
        WHEN NEW.room_key IS NULL OR NEW.room_key = '' OR NEW.room_key != replace(replace(NEW.building, ' 栋', ''), '栋', '') || '-' || NEW.room
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_ROOM_KEY');
        END;

        CREATE TRIGGER properties_payload_insert_guard
        BEFORE INSERT ON properties
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.building IS NULL OR trim(NEW.building) = ''
          OR NEW.room IS NULL OR trim(NEW.room) = ''
          OR NEW.layout IS NULL OR trim(NEW.layout) = ''
          OR NEW.area <= 0
          OR NEW.rent < 0
          OR json_valid(NEW.tags_json) = 0
          OR (NEW.lease_end IS NOT NULL AND (
              NEW.lease_end NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              OR CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
              OR CAST(substr(NEW.lease_end, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
                  WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
                  WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
                  WHEN (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
                  ELSE 28
                END
            ))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_PAYLOAD');
        END;

        CREATE TRIGGER properties_payload_update_guard
        BEFORE UPDATE ON properties
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.building IS NULL OR trim(NEW.building) = ''
          OR NEW.room IS NULL OR trim(NEW.room) = ''
          OR NEW.layout IS NULL OR trim(NEW.layout) = ''
          OR NEW.area <= 0
          OR NEW.rent < 0
          OR json_valid(NEW.tags_json) = 0
          OR (NEW.lease_end IS NOT NULL AND (
              NEW.lease_end NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              OR CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
              OR CAST(substr(NEW.lease_end, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
                  WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
                  WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
                  WHEN (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
                  ELSE 28
                END
            ))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_PAYLOAD');
        END;

        CREATE TRIGGER properties_relationship_insert_guard
        BEFORE INSERT ON properties
        WHEN NEW.status NOT IN ('occupied', 'vacant', 'reserved', 'maintenance')
          OR (NEW.status IN ('vacant', 'maintenance') AND (NEW.tenant IS NOT NULL OR NEW.lease_end IS NOT NULL))
          OR (NEW.status IN ('occupied', 'reserved') AND (NEW.tenant IS NULL OR NEW.lease_end IS NULL OR trim(NEW.tenant) = '' OR trim(NEW.lease_end) = ''))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_RELATIONSHIP');
        END;

        CREATE TRIGGER properties_relationship_update_guard
        BEFORE UPDATE OF status, tenant, lease_end ON properties
        WHEN NEW.status NOT IN ('occupied', 'vacant', 'reserved', 'maintenance')
          OR (NEW.status IN ('vacant', 'maintenance') AND (NEW.tenant IS NOT NULL OR NEW.lease_end IS NOT NULL))
          OR (NEW.status IN ('occupied', 'reserved') AND (NEW.tenant IS NULL OR NEW.lease_end IS NULL OR trim(NEW.tenant) = '' OR trim(NEW.lease_end) = ''))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_PROPERTY_RELATIONSHIP');
        END;

        CREATE TRIGGER properties_occupied_tenant_insert_guard
        BEFORE INSERT ON properties
        WHEN NEW.status = 'occupied'
          AND NOT EXISTS (
            SELECT 1 FROM tenants
            WHERE property_id = NEW.id
              AND status = 'active'
              AND name = NEW.tenant
              AND lease_end = NEW.lease_end
            LIMIT 1
          )
          AND NOT EXISTS (
            SELECT 1 FROM contracts
            WHERE property_id = NEW.id
              AND tenant = NEW.tenant
              AND end_date = NEW.lease_end
              AND status IN ('active', 'expiring')
            LIMIT 1
          )
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_TENANT_REQUIRED');
        END;

        CREATE TRIGGER properties_occupied_tenant_update_guard
        BEFORE UPDATE OF status, tenant, lease_end ON properties
        WHEN NEW.status = 'occupied'
          AND NOT EXISTS (
            SELECT 1 FROM tenants
            WHERE property_id = NEW.id
              AND status = 'active'
              AND name = NEW.tenant
              AND lease_end = NEW.lease_end
            LIMIT 1
          )
          AND NOT EXISTS (
            SELECT 1 FROM contracts
            WHERE property_id = NEW.id
              AND tenant = NEW.tenant
              AND end_date = NEW.lease_end
              AND status IN ('active', 'expiring')
            LIMIT 1
          )
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_TENANT_REQUIRED');
        END;

        CREATE TRIGGER properties_tenant_reference_update_guard
        BEFORE UPDATE OF status, tenant, lease_end ON properties
        WHEN (
            EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.id AND status = 'active' LIMIT 1)
            OR EXISTS (SELECT 1 FROM contracts WHERE property_id = OLD.id AND status != 'terminated' LIMIT 1)
            OR EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.id LIMIT 1)
            OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.id LIMIT 1)
          )
          AND NOT EXISTS (
              SELECT 1 FROM tenants
              WHERE property_id = OLD.id
                AND NEW.status = 'occupied'
                AND NEW.tenant = name
                AND NEW.lease_end = lease_end
          )
          AND NOT EXISTS (
              SELECT 1 FROM contracts
              WHERE property_id = OLD.id
                AND NEW.status = 'occupied'
                AND NEW.tenant = tenant
                AND NEW.lease_end = end_date
                AND status IN ('active', 'expiring')
          )
          AND NOT (
              NOT EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.id AND status = 'active' LIMIT 1)
              AND (
                  (
                      NEW.status = OLD.status
                      AND ((NEW.tenant = OLD.tenant) OR (NEW.tenant IS NULL AND OLD.tenant IS NULL))
                      AND ((NEW.lease_end = OLD.lease_end) OR (NEW.lease_end IS NULL AND OLD.lease_end IS NULL))
                  )
                  OR (
                      NEW.status = 'vacant'
                      AND NEW.tenant IS NULL
                      AND NEW.lease_end IS NULL
                  )
              )
          )
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER properties_room_reference_update_guard
        BEFORE UPDATE OF building, room, room_key ON properties
        WHEN OLD.room_key != NEW.room_key
          AND (
            EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.id AND status = 'active' LIMIT 1)
            OR EXISTS (SELECT 1 FROM contracts WHERE property_id = OLD.id LIMIT 1)
            OR EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.id LIMIT 1)
            OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.id LIMIT 1)
          )
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER properties_id_reference_update_guard
        BEFORE UPDATE OF id ON properties
        WHEN EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.id AND status = 'active' LIMIT 1)
          OR EXISTS (SELECT 1 FROM contracts WHERE property_id = OLD.id LIMIT 1)
          OR EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.id LIMIT 1)
          OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER properties_delete_reference_guard
        BEFORE DELETE ON properties
        WHEN EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.id AND status = 'active' LIMIT 1)
          OR EXISTS (SELECT 1 FROM contracts WHERE property_id = OLD.id LIMIT 1)
          OR EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.id LIMIT 1)
          OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER tenants_payload_insert_guard
        BEFORE INSERT ON tenants
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.name IS NULL OR trim(NEW.name) = ''
          OR NEW.phone IS NULL OR trim(NEW.phone) = ''
          OR NEW.contract_id IS NULL OR trim(NEW.contract_id) = ''
          OR NEW.move_in_date IS NULL OR trim(NEW.move_in_date) = ''
          OR NEW.lease_end IS NULL OR trim(NEW.lease_end) = ''
          OR NEW.payment_status NOT IN ('paid', 'pending', 'overdue', 'reconciled')
          OR NEW.status NOT IN ('active', 'moved_out')
          OR (NEW.status = 'active' AND NEW.move_out_date IS NOT NULL)
          OR (NEW.status = 'moved_out' AND (NEW.move_out_date IS NULL OR trim(NEW.move_out_date) = ''))
          OR (NEW.move_out_date IS NOT NULL AND NEW.move_out_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
          OR (NEW.move_out_date IS NOT NULL AND date(NEW.move_out_date) < date(NEW.move_in_date))
          OR NEW.balance < 0
          OR NEW.move_in_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR NEW.lease_end NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.move_in_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR CAST(substr(NEW.lease_end, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.lease_end) < date(NEW.move_in_date)
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_TENANT_PAYLOAD');
        END;

        CREATE TRIGGER tenants_payload_update_guard
        BEFORE UPDATE ON tenants
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.name IS NULL OR trim(NEW.name) = ''
          OR NEW.phone IS NULL OR trim(NEW.phone) = ''
          OR NEW.contract_id IS NULL OR trim(NEW.contract_id) = ''
          OR NEW.move_in_date IS NULL OR trim(NEW.move_in_date) = ''
          OR NEW.lease_end IS NULL OR trim(NEW.lease_end) = ''
          OR NEW.payment_status NOT IN ('paid', 'pending', 'overdue', 'reconciled')
          OR NEW.status NOT IN ('active', 'moved_out')
          OR (NEW.status = 'active' AND NEW.move_out_date IS NOT NULL)
          OR (NEW.status = 'moved_out' AND (NEW.move_out_date IS NULL OR trim(NEW.move_out_date) = ''))
          OR (NEW.move_out_date IS NOT NULL AND NEW.move_out_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
          OR (NEW.move_out_date IS NOT NULL AND date(NEW.move_out_date) < date(NEW.move_in_date))
          OR NEW.balance < 0
          OR NEW.move_in_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR NEW.lease_end NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.move_in_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.move_in_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.move_in_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR CAST(substr(NEW.lease_end, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.lease_end, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.lease_end, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.lease_end) < date(NEW.move_in_date)
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_TENANT_PAYLOAD');
        END;

        CREATE TRIGGER tenants_property_id_insert_guard
        BEFORE INSERT ON tenants
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER tenants_property_id_update_guard
        BEFORE UPDATE OF property_id ON tenants
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER tenants_property_available_insert_guard
        BEFORE INSERT ON tenants
        WHEN (SELECT status FROM properties WHERE id = NEW.property_id) != 'vacant'
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_ALREADY_OCCUPIED');
        END;

        CREATE TRIGGER tenants_property_available_update_guard
        BEFORE UPDATE OF property_id ON tenants
        WHEN NEW.property_id != OLD.property_id
          AND (SELECT status FROM properties WHERE id = NEW.property_id) != 'vacant'
        BEGIN
            SELECT RAISE(ABORT, 'PROPERTY_ALREADY_OCCUPIED');
        END;

        CREATE TRIGGER tenants_room_insert_guard
        BEFORE INSERT ON tenants
        WHEN NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
          OR NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER tenants_room_update_guard
        BEFORE UPDATE OF property_id, room ON tenants
        WHEN NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
          OR NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER tenants_property_insert_sync
        AFTER INSERT ON tenants
        WHEN NEW.status = 'active'
        BEGIN
            UPDATE properties
            SET tenant = NEW.name,
                lease_end = NEW.lease_end,
                status = 'occupied'
            WHERE id = NEW.property_id;
        END;

        CREATE TRIGGER tenants_property_update_sync
        AFTER UPDATE OF name, property_id, lease_end, status, move_out_date ON tenants
        BEGIN
            UPDATE properties
            SET tenant = NULL,
                lease_end = NULL,
                status = 'vacant'
            WHERE id = OLD.property_id
              AND OLD.property_id != NEW.property_id
              AND NOT EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.property_id AND status = 'active');

            UPDATE properties
            SET tenant = NEW.name,
                lease_end = NEW.lease_end,
                status = 'occupied'
            WHERE id = NEW.property_id
              AND NEW.status = 'active';

            UPDATE properties
            SET tenant = NULL,
                lease_end = NULL,
                status = 'vacant'
            WHERE id = NEW.property_id
              AND NEW.status != 'active'
              AND NOT EXISTS (SELECT 1 FROM tenants WHERE property_id = NEW.property_id AND status = 'active');
        END;

        CREATE TRIGGER tenants_property_delete_sync
        AFTER DELETE ON tenants
        WHEN NOT EXISTS (SELECT 1 FROM tenants WHERE property_id = OLD.property_id AND status = 'active')
        BEGIN
            UPDATE properties
            SET tenant = NULL,
                lease_end = NULL,
                status = 'vacant'
            WHERE id = OLD.property_id;
        END;

        CREATE TRIGGER tenants_contract_insert_conflict_guard
        BEFORE INSERT ON tenants
        WHEN EXISTS (
            SELECT 1 FROM contracts
            WHERE status != 'terminated'
              AND (id = NEW.contract_id OR property_id = NEW.property_id OR room = NEW.room)
              AND NOT (id = NEW.contract_id AND property_id = NEW.property_id AND room = NEW.room AND tenant = NEW.name)
            LIMIT 1
        )
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_CONTRACTS');
        END;

        CREATE TRIGGER tenants_contract_update_conflict_guard
        BEFORE UPDATE OF name, contract_id, property_id, room ON tenants
        WHEN EXISTS (
            SELECT 1 FROM contracts
            WHERE status != 'terminated'
              AND (id = NEW.contract_id OR property_id = NEW.property_id OR room = NEW.room)
              AND NOT (id = NEW.contract_id AND property_id = NEW.property_id AND room = NEW.room AND tenant = NEW.name)
            LIMIT 1
        )
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_CONTRACTS');
        END;

        CREATE TRIGGER tenants_contract_delete_guard
        BEFORE DELETE ON tenants
        WHEN EXISTS (SELECT 1 FROM contracts WHERE id = OLD.contract_id OR property_id = OLD.property_id OR room = OLD.room LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_RELATED_CONTRACTS');
        END;

        CREATE TRIGGER tenants_activity_delete_guard
        BEFORE DELETE ON tenants
        WHEN EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.property_id OR room = OLD.room OR tenant = OLD.name LIMIT 1)
          OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.property_id OR room = OLD.room OR tenant = OLD.name LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER tenants_contract_identity_update_guard
        BEFORE UPDATE OF name, contract_id, property_id, room ON tenants
        WHEN (OLD.name != NEW.name OR OLD.contract_id != NEW.contract_id OR OLD.property_id != NEW.property_id OR OLD.room != NEW.room)
          AND EXISTS (SELECT 1 FROM contracts WHERE id = OLD.contract_id OR property_id = OLD.property_id OR room = OLD.room LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_CONTRACTS');
        END;

        CREATE TRIGGER tenants_activity_identity_update_guard
        BEFORE UPDATE OF name, contract_id, property_id, room ON tenants
        WHEN (OLD.name != NEW.name OR OLD.contract_id != NEW.contract_id OR OLD.property_id != NEW.property_id OR OLD.room != NEW.room)
          AND (
            EXISTS (SELECT 1 FROM maintenance_orders WHERE property_id = OLD.property_id OR room = OLD.room OR tenant = OLD.name LIMIT 1)
            OR EXISTS (SELECT 1 FROM finance_transactions WHERE property_id = OLD.property_id OR room = OLD.room OR tenant = OLD.name LIMIT 1)
          )
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_RELATED_RECORDS');
        END;

        CREATE TRIGGER contracts_payload_insert_guard
        BEFORE INSERT ON contracts
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = ''
          OR NEW.start_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.start_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.start_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.start_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.start_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.end_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.end_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.end_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.end_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.end_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.end_date) < date(NEW.start_date)
          OR NEW.monthly_rent < 0
          OR NEW.deposit < 0
          OR NEW.days_left < 0
          OR NEW.status NOT IN ('active', 'pending', 'expiring', 'terminated')
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_PAYLOAD');
        END;

        CREATE TRIGGER contracts_initial_status_insert_guard
        BEFORE INSERT ON contracts
        WHEN NEW.status != 'pending'
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_STATUS');
        END;

        CREATE TRIGGER contracts_payload_update_guard
        BEFORE UPDATE ON contracts
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = ''
          OR NEW.start_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.start_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.start_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.start_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.start_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.start_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.end_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.end_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.end_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.end_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.end_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.end_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.end_date) < date(NEW.start_date)
          OR NEW.monthly_rent < 0
          OR NEW.deposit < 0
          OR NEW.days_left < 0
          OR NEW.status NOT IN ('active', 'pending', 'expiring', 'terminated')
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_PAYLOAD');
        END;

        CREATE TRIGGER contracts_property_id_insert_guard
        BEFORE INSERT ON contracts
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER contracts_property_id_update_guard
        BEFORE UPDATE OF property_id ON contracts
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER contracts_room_insert_guard
        BEFORE INSERT ON contracts
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER contracts_room_update_guard
        BEFORE UPDATE OF property_id, room ON contracts
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER contracts_unique_property_insert_guard
        BEFORE INSERT ON contracts
        WHEN NEW.status != 'terminated'
          AND EXISTS (
            SELECT 1 FROM contracts
            WHERE status != 'terminated'
              AND (property_id = NEW.property_id OR room = NEW.room)
            LIMIT 1
          )
        BEGIN
            SELECT RAISE(ABORT, 'CONTRACT_ALREADY_EXISTS_FOR_PROPERTY');
        END;

        CREATE TRIGGER contracts_unique_property_update_guard
        BEFORE UPDATE OF property_id, room, status ON contracts
        WHEN NEW.status != 'terminated'
          AND EXISTS (
            SELECT 1 FROM contracts
            WHERE id != OLD.id
              AND status != 'terminated'
              AND (property_id = NEW.property_id OR room = NEW.room)
            LIMIT 1
          )
        BEGIN
            SELECT RAISE(ABORT, 'CONTRACT_ALREADY_EXISTS_FOR_PROPERTY');
        END;

        CREATE TRIGGER contracts_tenant_insert_conflict_guard
        BEFORE INSERT ON contracts
        WHEN EXISTS (
            SELECT 1 FROM tenants
            WHERE status = 'active'
              AND (contract_id = NEW.id OR property_id = NEW.property_id OR room = NEW.room)
              AND NOT (contract_id = NEW.id AND property_id = NEW.property_id AND room = NEW.room AND name = NEW.tenant)
            LIMIT 1
        )
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_CONTRACTS');
        END;

        CREATE TRIGGER contracts_tenant_update_conflict_guard
        BEFORE UPDATE OF id, tenant, property_id, room ON contracts
        WHEN EXISTS (
            SELECT 1 FROM tenants
            WHERE status = 'active'
              AND (contract_id = NEW.id OR property_id = NEW.property_id OR room = NEW.room)
              AND NOT (contract_id = NEW.id AND property_id = NEW.property_id AND room = NEW.room AND name = NEW.tenant)
            LIMIT 1
        )
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_CONTRACTS');
        END;

        CREATE TRIGGER contracts_tenant_termination_guard
        BEFORE UPDATE OF status ON contracts
        WHEN NEW.status = 'terminated'
          AND OLD.status != 'terminated'
          AND EXISTS (
            SELECT 1 FROM tenants
            WHERE status = 'active'
              AND contract_id = OLD.id
              AND property_id = OLD.property_id
              AND room = OLD.room
              AND name = OLD.tenant
            LIMIT 1
          )
          AND NOT EXISTS (SELECT 1 FROM move_outs WHERE contract_id = OLD.id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'TENANT_HAS_RELATED_CONTRACTS');
        END;

        CREATE TRIGGER contracts_status_transition_guard
        BEFORE UPDATE OF status ON contracts
        WHEN OLD.status != NEW.status
          AND NOT (
            (OLD.status = 'pending' AND NEW.status IN ('active', 'terminated'))
            OR (OLD.status IN ('active', 'expiring') AND NEW.status = 'terminated')
          )
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_STATUS');
        END;

        CREATE TRIGGER contracts_non_pending_update_guard
        BEFORE UPDATE OF tenant, property_id, room, start_date, end_date, monthly_rent, deposit ON contracts
        WHEN OLD.status != 'pending'
          AND (
            OLD.tenant != NEW.tenant
            OR OLD.property_id != NEW.property_id
            OR OLD.room != NEW.room
            OR OLD.start_date != NEW.start_date
            OR OLD.end_date != NEW.end_date
            OR OLD.monthly_rent != NEW.monthly_rent
            OR OLD.deposit != NEW.deposit
          )
          AND NOT EXISTS (
            SELECT 1 FROM contract_renewals
            WHERE contract_id = OLD.id
              AND new_end_date = NEW.end_date
              AND monthly_rent = NEW.monthly_rent
              AND deposit = NEW.deposit
            LIMIT 1
          )
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_STATUS');
        END;

        CREATE TRIGGER contracts_delete_guard
        BEFORE DELETE ON contracts
        BEGIN
            SELECT RAISE(ABORT, 'CONTRACT_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER contracts_property_insert_sync
        AFTER INSERT ON contracts
        WHEN NEW.status IN ('active', 'expiring')
        BEGIN
            UPDATE properties
            SET tenant = NEW.tenant,
                lease_end = NEW.end_date,
                status = 'occupied'
            WHERE id = NEW.property_id;
        END;

        CREATE TRIGGER contracts_property_update_sync
        AFTER UPDATE OF status, tenant, end_date, property_id, room ON contracts
        WHEN NEW.status IN ('active', 'expiring')
        BEGIN
            UPDATE properties
            SET tenant = NEW.tenant,
                lease_end = NEW.end_date,
                status = 'occupied'
            WHERE id = NEW.property_id;
        END;

        CREATE TRIGGER contracts_property_terminate_sync
        AFTER UPDATE OF status ON contracts
        WHEN NEW.status = 'terminated'
          AND OLD.status != 'terminated'
          AND NOT EXISTS (
            SELECT 1 FROM contracts
            WHERE id != NEW.id
              AND property_id = NEW.property_id
              AND status IN ('active', 'expiring', 'pending')
            LIMIT 1
          )
          AND NOT EXISTS (SELECT 1 FROM tenants WHERE property_id = NEW.property_id AND status = 'active' LIMIT 1)
        BEGIN
            UPDATE properties
            SET tenant = NULL,
                lease_end = NULL,
                status = 'vacant'
            WHERE id = NEW.property_id;
        END;

        CREATE TRIGGER maintenance_orders_payload_insert_guard
        BEFORE INSERT ON maintenance_orders
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.title IS NULL OR trim(NEW.title) = '' OR length(trim(NEW.title)) > 120
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = '' OR length(trim(NEW.tenant)) > 60
          OR NEW.category IS NULL OR trim(NEW.category) = '' OR length(trim(NEW.category)) > 40
          OR NEW.priority NOT IN ('low', 'medium', 'high', 'urgent')
          OR NEW.status NOT IN ('open', 'in_progress', 'resolved')
          OR NEW.assignee IS NULL OR trim(NEW.assignee) = '' OR length(trim(NEW.assignee)) > 60
          OR NEW.created_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.created_at, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.created_at, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.due_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.due_at, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.due_at, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.due_at, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.due_at, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.due_at) < date(NEW.created_at)
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_PAYLOAD');
        END;

        CREATE TRIGGER maintenance_orders_payload_update_guard
        BEFORE UPDATE ON maintenance_orders
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.title IS NULL OR trim(NEW.title) = '' OR length(trim(NEW.title)) > 120
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = '' OR length(trim(NEW.tenant)) > 60
          OR NEW.category IS NULL OR trim(NEW.category) = '' OR length(trim(NEW.category)) > 40
          OR NEW.priority NOT IN ('low', 'medium', 'high', 'urgent')
          OR NEW.status NOT IN ('open', 'in_progress', 'resolved')
          OR NEW.assignee IS NULL OR trim(NEW.assignee) = '' OR length(trim(NEW.assignee)) > 60
          OR NEW.created_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.created_at, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.created_at, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.due_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.due_at, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.due_at, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.due_at, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.due_at, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.due_at, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.due_at) < date(NEW.created_at)
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_PAYLOAD');
        END;

        CREATE TRIGGER maintenance_orders_initial_status_insert_guard
        BEFORE INSERT ON maintenance_orders
        WHEN NEW.status != 'open'
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_STATUS');
        END;

        CREATE TRIGGER maintenance_orders_status_transition_guard
        BEFORE UPDATE OF status ON maintenance_orders
        WHEN OLD.status != NEW.status
          AND NOT (
            (OLD.status = 'open' AND NEW.status = 'in_progress' AND NEW.assignee != OLD.assignee AND NEW.assignee != '未分配')
            OR (OLD.status = 'in_progress' AND NEW.status = 'resolved')
          )
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_STATUS');
        END;

        CREATE TRIGGER maintenance_orders_immutable_update_guard
        BEFORE UPDATE OF id, property_id, room, title, tenant, category, priority, created_at, due_at ON maintenance_orders
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_STATUS');
        END;

        CREATE TRIGGER maintenance_orders_assignee_update_guard
        BEFORE UPDATE OF assignee ON maintenance_orders
        WHEN NOT (OLD.status = 'open' AND NEW.status = 'in_progress' AND NEW.assignee != '未分配')
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MAINTENANCE_STATUS');
        END;

        CREATE TRIGGER maintenance_orders_delete_guard
        BEFORE DELETE ON maintenance_orders
        BEGIN
            SELECT RAISE(ABORT, 'MAINTENANCE_ORDER_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER maintenance_orders_property_id_insert_guard
        BEFORE INSERT ON maintenance_orders
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER maintenance_orders_property_id_update_guard
        BEFORE UPDATE OF property_id ON maintenance_orders
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER maintenance_orders_room_insert_guard
        BEFORE INSERT ON maintenance_orders
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER maintenance_orders_room_update_guard
        BEFORE UPDATE OF property_id, room ON maintenance_orders
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER finance_transactions_payload_insert_guard
        BEFORE INSERT ON finance_transactions
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.type IS NULL OR trim(NEW.type) = '' OR length(trim(NEW.type)) > 40
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = '' OR length(trim(NEW.tenant)) > 60
          OR NEW.amount = 0
          OR NEW.method IS NULL OR trim(NEW.method) = '' OR length(trim(NEW.method)) > 40
          OR NEW.status NOT IN ('paid', 'pending', 'overdue')
          OR NEW.note IS NULL OR length(trim(NEW.note)) > 120
          OR (NEW.lifecycle_type IS NOT NULL AND NEW.lifecycle_type NOT IN ('rent', 'renewal', 'settlement'))
          OR (NEW.lifecycle_type = 'settlement' AND NOT EXISTS (
            SELECT 1 FROM deposit_settlements
            WHERE id = NEW.settlement_id
              AND finance_transaction_id = NEW.id
              AND id = NEW.id
              AND property_id = NEW.property_id
              AND contract_id = NEW.contract_id
              AND room = NEW.room
              AND tenant = NEW.tenant
              AND settled_date = NEW.date
              AND refund_amount = -NEW.amount
              AND NEW.type = '押金退还'
              AND method = NEW.method
              AND note = NEW.note
              AND NEW.status = 'paid'
            LIMIT 1
          ))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_FINANCE_PAYLOAD');
        END;

        CREATE TRIGGER finance_transactions_payload_update_guard
        BEFORE UPDATE ON finance_transactions
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.type IS NULL OR trim(NEW.type) = '' OR length(trim(NEW.type)) > 40
          OR NEW.tenant IS NULL OR trim(NEW.tenant) = '' OR length(trim(NEW.tenant)) > 60
          OR NEW.amount = 0
          OR NEW.method IS NULL OR trim(NEW.method) = '' OR length(trim(NEW.method)) > 40
          OR NEW.status NOT IN ('paid', 'pending', 'overdue', 'reconciled')
          OR (OLD.status = 'reconciled' AND NEW.status != 'reconciled')
          OR (NEW.status = 'reconciled' AND NOT EXISTS (SELECT 1 FROM reconciliation_records WHERE system_flow_id = NEW.id AND status = 'matched' AND amount = NEW.amount AND date = NEW.date AND payer = NEW.tenant AND channel = NEW.method LIMIT 1))
          OR (NEW.status != 'reconciled' AND EXISTS (SELECT 1 FROM reconciliation_records WHERE system_flow_id = NEW.id AND status = 'matched' LIMIT 1))
          OR NEW.note IS NULL OR length(trim(NEW.note)) > 120
          OR (NEW.lifecycle_type IS NOT NULL AND NEW.lifecycle_type NOT IN ('rent', 'renewal', 'settlement'))
          OR (NEW.lifecycle_type = 'settlement' AND NOT EXISTS (
            SELECT 1 FROM deposit_settlements
            WHERE id = NEW.settlement_id
              AND finance_transaction_id = NEW.id
              AND id = NEW.id
              AND property_id = NEW.property_id
              AND contract_id = NEW.contract_id
              AND room = NEW.room
              AND tenant = NEW.tenant
              AND settled_date = NEW.date
              AND refund_amount = -NEW.amount
              AND NEW.type = '押金退还'
              AND method = NEW.method
              AND note = NEW.note
              AND NEW.status = 'paid'
            LIMIT 1
          ))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_FINANCE_PAYLOAD');
        END;

        CREATE TRIGGER finance_transactions_property_id_insert_guard
        BEFORE INSERT ON finance_transactions
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER finance_transactions_property_id_update_guard
        BEFORE UPDATE OF property_id ON finance_transactions
        WHEN NEW.property_id IS NULL OR NOT EXISTS (SELECT 1 FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER finance_transactions_room_insert_guard
        BEFORE INSERT ON finance_transactions
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER finance_transactions_room_update_guard
        BEFORE UPDATE OF property_id, room ON finance_transactions
        WHEN NEW.room != (SELECT room_key FROM properties WHERE id = NEW.property_id)
        BEGIN
            SELECT RAISE(ABORT, 'RELATED_PROPERTY_REQUIRED');
        END;

        CREATE TRIGGER finance_transactions_reserved_id_insert_guard
        BEFORE INSERT ON finance_transactions
        WHEN (NEW.id GLOB 'RENT-*' AND COALESCE(NEW.lifecycle_type, '') != 'rent')
          OR (NEW.id GLOB 'SETTLE-*' AND COALESCE(NEW.lifecycle_type, '') != 'settlement')
          OR (NEW.id GLOB 'RENEWAL-*' AND COALESCE(NEW.lifecycle_type, '') != 'renewal')
        BEGIN
            SELECT RAISE(ABORT, 'RESERVED_FINANCE_TRANSACTION_ID');
        END;

        CREATE TRIGGER finance_transactions_reserved_id_update_guard
        BEFORE UPDATE OF id, lifecycle_type ON finance_transactions
        WHEN (NEW.id GLOB 'RENT-*' AND COALESCE(NEW.lifecycle_type, '') != 'rent')
          OR (NEW.id GLOB 'SETTLE-*' AND COALESCE(NEW.lifecycle_type, '') != 'settlement')
          OR (NEW.id GLOB 'RENEWAL-*' AND COALESCE(NEW.lifecycle_type, '') != 'renewal')
        BEGIN
            SELECT RAISE(ABORT, 'RESERVED_FINANCE_TRANSACTION_ID');
        END;

        CREATE TRIGGER finance_transactions_reconciled_immutable_update_guard
        BEFORE UPDATE ON finance_transactions
        WHEN (OLD.status = 'reconciled' OR EXISTS (SELECT 1 FROM deposit_settlements WHERE finance_transaction_id = OLD.id LIMIT 1))
          AND (
            NEW.id != OLD.id
            OR NEW.property_id != OLD.property_id
            OR NEW.date != OLD.date
            OR NEW.type != OLD.type
            OR NEW.room != OLD.room
            OR NEW.tenant != OLD.tenant
            OR NEW.amount != OLD.amount
            OR NEW.method != OLD.method
            OR NEW.status != OLD.status
            OR NEW.note != OLD.note
            OR COALESCE(NEW.contract_id, '') != COALESCE(OLD.contract_id, '')
            OR COALESCE(NEW.settlement_id, '') != COALESCE(OLD.settlement_id, '')
            OR COALESCE(NEW.lifecycle_type, '') != COALESCE(OLD.lifecycle_type, '')
          )
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_FINANCE_PAYLOAD');
        END;

        CREATE TRIGGER finance_transactions_reconciliation_delete_guard
        BEFORE DELETE ON finance_transactions
        WHEN OLD.status = 'reconciled'
          OR EXISTS (SELECT 1 FROM reconciliation_records WHERE system_flow_id = OLD.id LIMIT 1)
          OR EXISTS (SELECT 1 FROM deposit_settlements WHERE finance_transaction_id = OLD.id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'FINANCE_TRANSACTION_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER reconciliation_records_payload_insert_guard
        BEFORE INSERT ON reconciliation_records
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.bank_flow_id IS NULL OR trim(NEW.bank_flow_id) = '' OR length(trim(NEW.bank_flow_id)) > 60
          OR NEW.system_flow_id IS NULL OR trim(NEW.system_flow_id) = '' OR length(trim(NEW.system_flow_id)) > 60
          OR NEW.payer IS NULL OR trim(NEW.payer) = '' OR length(trim(NEW.payer)) > 60
          OR NEW.amount = 0
          OR NEW.channel IS NULL OR trim(NEW.channel) = '' OR length(trim(NEW.channel)) > 40
          OR NEW.status NOT IN ('matched', 'pending', 'exception', 'reviewed')
          OR NEW.status = 'reviewed'
          OR (NEW.status = 'matched' AND NEW.difference != 0)
          OR (NEW.status = 'matched' AND NOT EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id AND amount = NEW.amount AND date = NEW.date AND tenant = NEW.payer AND method = NEW.channel AND status = 'paid' LIMIT 1))
          OR (NEW.status = 'exception' AND NOT EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id AND (amount != NEW.amount OR date != NEW.date OR tenant != NEW.payer OR method != NEW.channel OR status != 'paid') LIMIT 1))
          OR (NEW.status = 'pending' AND NEW.difference != 0)
          OR (NEW.status = 'pending' AND EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id LIMIT 1))
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_RECONCILIATION_PAYLOAD');
        END;

        CREATE TRIGGER reconciliation_records_payload_update_guard
        BEFORE UPDATE ON reconciliation_records
        WHEN NEW.id IS NULL OR trim(NEW.id) = '' OR length(trim(NEW.id)) > 40
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.bank_flow_id IS NULL OR trim(NEW.bank_flow_id) = '' OR length(trim(NEW.bank_flow_id)) > 60
          OR NEW.system_flow_id IS NULL OR trim(NEW.system_flow_id) = '' OR length(trim(NEW.system_flow_id)) > 60
          OR NEW.payer IS NULL OR trim(NEW.payer) = '' OR length(trim(NEW.payer)) > 60
          OR NEW.amount = 0
          OR NEW.channel IS NULL OR trim(NEW.channel) = '' OR length(trim(NEW.channel)) > 40
          OR NEW.status NOT IN ('matched', 'pending', 'exception', 'reviewed')
          OR (NEW.status = 'matched' AND NEW.difference != 0)
          OR (NEW.status = 'matched' AND NOT EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id AND amount = NEW.amount AND date = NEW.date AND tenant = NEW.payer AND method = NEW.channel AND status = 'paid' LIMIT 1))
          OR (NEW.status = 'exception' AND NOT EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id AND (amount != NEW.amount OR date != NEW.date OR tenant != NEW.payer OR method != NEW.channel OR status != 'paid') LIMIT 1))
          OR (NEW.status = 'pending' AND NEW.difference != 0)
          OR (NEW.status = 'pending' AND EXISTS (SELECT 1 FROM finance_transactions WHERE id = NEW.system_flow_id LIMIT 1))
          OR (NEW.status = 'reviewed' AND OLD.status != 'exception')
          OR (OLD.status = 'reviewed')
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_RECONCILIATION_PAYLOAD');
        END;

        CREATE TRIGGER reconciliation_records_bank_flow_insert_guard
        BEFORE INSERT ON reconciliation_records
        WHEN EXISTS (SELECT 1 FROM reconciliation_records WHERE bank_flow_id = NEW.bank_flow_id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_FLOW_ALREADY_EXISTS');
        END;

        CREATE TRIGGER reconciliation_records_bank_flow_update_guard
        BEFORE UPDATE OF bank_flow_id ON reconciliation_records
        WHEN EXISTS (SELECT 1 FROM reconciliation_records WHERE id != NEW.id AND bank_flow_id = NEW.bank_flow_id LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_FLOW_ALREADY_EXISTS');
        END;

        CREATE TRIGGER reconciliation_records_system_flow_insert_guard
        BEFORE INSERT ON reconciliation_records
        WHEN NEW.status IN ('matched', 'exception')
          AND EXISTS (SELECT 1 FROM reconciliation_records WHERE system_flow_id = NEW.system_flow_id AND status IN ('matched', 'exception') LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_FLOW_ALREADY_EXISTS');
        END;

        CREATE TRIGGER reconciliation_records_system_flow_update_guard
        BEFORE UPDATE OF system_flow_id, status ON reconciliation_records
        WHEN NEW.status IN ('matched', 'exception')
          AND EXISTS (SELECT 1 FROM reconciliation_records WHERE id != NEW.id AND system_flow_id = NEW.system_flow_id AND status IN ('matched', 'exception') LIMIT 1)
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_FLOW_ALREADY_EXISTS');
        END;

        CREATE TRIGGER reconciliation_records_matched_insert_sync
        AFTER INSERT ON reconciliation_records
        WHEN NEW.status = 'matched'
        BEGIN
            UPDATE finance_transactions
            SET status = 'reconciled'
            WHERE id = NEW.system_flow_id;
        END;

        CREATE TRIGGER reconciliation_records_matched_update_sync
        AFTER UPDATE OF status ON reconciliation_records
        WHEN OLD.status != 'matched' AND NEW.status = 'matched'
        BEGIN
            UPDATE finance_transactions
            SET status = 'reconciled'
            WHERE id = NEW.system_flow_id;
        END;

        CREATE TRIGGER reconciliation_records_matched_update_guard
        BEFORE UPDATE ON reconciliation_records
        WHEN OLD.status = 'matched'
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_MATCHED_IMMUTABLE');
        END;

        CREATE TRIGGER reconciliation_records_matched_delete_guard
        BEFORE DELETE ON reconciliation_records
        WHEN OLD.status = 'matched'
        BEGIN
            SELECT RAISE(ABORT, 'RECONCILIATION_MATCHED_IMMUTABLE');
        END;


        CREATE TRIGGER contract_renewals_payload_insert_guard
        BEFORE INSERT ON contract_renewals
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NOT EXISTS (
            SELECT 1 FROM contracts
            WHERE id = NEW.contract_id
              AND property_id = NEW.property_id
              AND room = NEW.room
              AND tenant = NEW.tenant
              AND status IN ('active', 'expiring')
              AND end_date = NEW.old_end_date
          )
          OR NEW.old_end_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.old_end_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.old_end_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.old_end_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.old_end_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.old_end_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.old_end_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.old_end_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.new_end_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.new_end_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.new_end_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.new_end_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.new_end_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.new_end_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.new_end_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.new_end_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR date(NEW.new_end_date) <= date(NEW.old_end_date)
          OR NEW.monthly_rent < 0
          OR NEW.deposit < 0
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_CONTRACT_PAYLOAD');
        END;

        CREATE TRIGGER contract_renewals_update_guard
        BEFORE UPDATE ON contract_renewals
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_UPDATE_FORBIDDEN');
        END;

        CREATE TRIGGER contract_renewals_delete_guard
        BEFORE DELETE ON contract_renewals
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER move_outs_payload_insert_guard
        BEFORE INSERT ON move_outs
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NOT EXISTS (
            SELECT 1 FROM contracts
            WHERE id = NEW.contract_id
              AND property_id = NEW.property_id
              AND room = NEW.room
              AND tenant = NEW.tenant
              AND status IN ('active', 'expiring')
          )
          OR EXISTS (SELECT 1 FROM move_outs WHERE contract_id = NEW.contract_id LIMIT 1)
          OR NEW.move_out_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.move_out_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.move_out_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.move_out_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.move_out_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.move_out_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.move_out_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.move_out_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.status NOT IN ('pending_settlement', 'settled')
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_MOVE_OUT_PAYLOAD');
        END;

        CREATE TRIGGER move_outs_update_guard
        BEFORE UPDATE ON move_outs
        WHEN NOT (
            OLD.status = 'pending_settlement'
            AND NEW.status = 'settled'
            AND NEW.id = OLD.id
            AND NEW.contract_id = OLD.contract_id
            AND NEW.property_id = OLD.property_id
            AND NEW.tenant = OLD.tenant
            AND NEW.room = OLD.room
            AND NEW.move_out_date = OLD.move_out_date
            AND NEW.reason = OLD.reason
            AND NEW.created_at = OLD.created_at
            AND EXISTS (SELECT 1 FROM deposit_settlements WHERE move_out_id = OLD.id LIMIT 1)
        )
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_UPDATE_FORBIDDEN');
        END;

        CREATE TRIGGER move_outs_delete_guard
        BEFORE DELETE ON move_outs
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER deposit_settlements_payload_insert_guard
        BEFORE INSERT ON deposit_settlements
        WHEN NEW.id IS NULL OR trim(NEW.id) = ''
          OR NOT EXISTS (SELECT 1 FROM move_outs WHERE id = NEW.move_out_id AND contract_id = NEW.contract_id AND property_id = NEW.property_id AND room = NEW.room AND tenant = NEW.tenant)
          OR NOT EXISTS (SELECT 1 FROM contracts WHERE id = NEW.contract_id AND property_id = NEW.property_id AND room = NEW.room AND tenant = NEW.tenant AND deposit = NEW.deposit LIMIT 1)
          OR EXISTS (SELECT 1 FROM deposit_settlements WHERE move_out_id = NEW.move_out_id LIMIT 1)
          OR NEW.deposit < 0
          OR NEW.deductions < 0
          OR NEW.rent_deduction < 0
          OR NEW.utility_deduction < 0
          OR NEW.damage_deduction < 0
          OR NEW.cleaning_deduction < 0
          OR NEW.other_deduction < 0
          OR NEW.deductions > NEW.deposit
          OR (NEW.rent_deduction + NEW.utility_deduction + NEW.damage_deduction + NEW.cleaning_deduction + NEW.other_deduction != NEW.deductions)
          OR NEW.refund_amount < 0
          OR NEW.refund_amount != NEW.deposit - NEW.deductions
          OR NEW.settled_date IS NULL
          OR NEW.settled_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
          OR CAST(substr(NEW.settled_date, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.settled_date, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.settled_date, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.settled_date, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.settled_date, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.settled_date, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.settled_date, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
          OR NEW.settled_date < (SELECT move_out_date FROM move_outs WHERE id = NEW.move_out_id)
          OR NEW.status NOT IN ('settled')
          OR NEW.method IS NULL OR trim(NEW.method) = '' OR length(trim(NEW.method)) > 40
          OR NEW.note IS NULL OR length(trim(NEW.note)) > 120
          OR (NEW.refund_amount = 0 AND NEW.finance_transaction_id IS NOT NULL)
          OR (NEW.refund_amount > 0 AND NEW.finance_transaction_id != NEW.id)
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_SETTLEMENT_PAYLOAD');
        END;

        CREATE TRIGGER deposit_settlements_insert_sync
        AFTER INSERT ON deposit_settlements
        BEGIN
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note, contract_id, settlement_id, lifecycle_type)
            SELECT NEW.id, NEW.property_id, NEW.settled_date, '押金退还', NEW.room, NEW.tenant, -NEW.refund_amount, NEW.method, 'paid', NEW.note, NEW.contract_id, NEW.id, 'settlement'
            WHERE NEW.refund_amount > 0;

            UPDATE move_outs SET status = 'settled' WHERE id = NEW.move_out_id;
        END;

        CREATE TRIGGER deposit_settlements_update_guard
        BEFORE UPDATE ON deposit_settlements
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_UPDATE_FORBIDDEN');
        END;

        CREATE TRIGGER deposit_settlements_delete_guard
        BEFORE DELETE ON deposit_settlements
        BEGIN
            SELECT RAISE(ABORT, 'LIFECYCLE_RECORD_DELETE_FORBIDDEN');
        END;

        CREATE TRIGGER audit_logs_insert_guard
        BEFORE INSERT ON audit_logs
        WHEN NEW.actor_id IS NULL OR trim(NEW.actor_id) = '' OR length(trim(NEW.actor_id)) > 80
          OR NEW.actor_name IS NULL OR trim(NEW.actor_name) = '' OR length(trim(NEW.actor_name)) > 80
          OR NEW.actor_role IS NULL OR trim(NEW.actor_role) = '' OR length(trim(NEW.actor_role)) > 40
          OR NEW.action IS NULL OR trim(NEW.action) = '' OR length(trim(NEW.action)) > 40
          OR NEW.resource_type IS NULL OR trim(NEW.resource_type) = '' OR length(trim(NEW.resource_type)) > 60
          OR NEW.resource_id IS NULL OR trim(NEW.resource_id) = '' OR length(trim(NEW.resource_id)) > 80
          OR NEW.created_at IS NULL OR trim(NEW.created_at) = ''
          OR length(NEW.created_at) != 32
          OR NEW.created_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]+00:00'
          OR CAST(substr(NEW.created_at, 12, 2) AS INTEGER) NOT BETWEEN 0 AND 23
          OR CAST(substr(NEW.created_at, 15, 2) AS INTEGER) NOT BETWEEN 0 AND 59
          OR CAST(substr(NEW.created_at, 18, 2) AS INTEGER) NOT BETWEEN 0 AND 59
          OR CAST(substr(NEW.created_at, 6, 2) AS INTEGER) NOT BETWEEN 1 AND 12
          OR CAST(substr(NEW.created_at, 9, 2) AS INTEGER) NOT BETWEEN 1 AND CASE
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (1, 3, 5, 7, 8, 10, 12) THEN 31
              WHEN CAST(substr(NEW.created_at, 6, 2) AS INTEGER) IN (4, 6, 9, 11) THEN 30
              WHEN (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 400 = 0 OR (CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 4 = 0 AND CAST(substr(NEW.created_at, 1, 4) AS INTEGER) % 100 != 0)) THEN 29
              ELSE 28
            END
        BEGIN
            SELECT RAISE(ABORT, 'INVALID_AUDIT_LOG_PAYLOAD');
        END;

        CREATE TRIGGER audit_logs_update_guard
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'AUDIT_LOG_IMMUTABLE');
        END;

        CREATE TRIGGER audit_logs_delete_guard
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'AUDIT_LOG_IMMUTABLE');
        END;
        COMMIT;
        """
        )
    except sqlite3.Error:
        db.rollback()
        raise


def _validate_schema(db: sqlite3.Connection) -> None:
    for table, expected_columns in EXPECTED_SCHEMA.items():
        table_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not table_exists:
            raise RuntimeError(f"Database schema is missing table {table}")

        actual_columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise RuntimeError(f"Database schema table {table} is missing columns: {', '.join(sorted(missing_columns))}")


def init_db() -> None:
    with get_connection() as db:
        current_version = db.execute("PRAGMA user_version").fetchone()[0]
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema version {current_version} is newer than supported version {SCHEMA_VERSION}")

        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS roles (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                built_in INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS permission_resources (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT NOT NULL,
                group_key TEXT NOT NULL,
                group_label TEXT NOT NULL,
                type TEXT NOT NULL,
                route TEXT,
                menu_label TEXT,
                menu_hint TEXT,
                sort INTEGER NOT NULL DEFAULT 1000,
                built_in INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS role_permissions (
                role_key TEXT NOT NULL REFERENCES roles(key) ON DELETE CASCADE,
                permission_key TEXT NOT NULL REFERENCES permission_resources(key) ON DELETE CASCADE,
                PRIMARY KEY (role_key, permission_key)
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role_key TEXT NOT NULL REFERENCES roles(key),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                building TEXT NOT NULL,
                room TEXT NOT NULL,
                room_key TEXT NOT NULL UNIQUE,
                layout TEXT NOT NULL,
                area REAL NOT NULL,
                rent INTEGER NOT NULL,
                status TEXT NOT NULL,
                tenant TEXT,
                lease_end TEXT,
                tags_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                property_id TEXT REFERENCES properties(id) ON DELETE RESTRICT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                room TEXT NOT NULL,
                contract_id TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                move_in_date TEXT NOT NULL,
                lease_end TEXT NOT NULL,
                balance INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                move_out_date TEXT
            );

            CREATE TABLE IF NOT EXISTS tenant_accounts (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                openid TEXT UNIQUE NOT NULL,
                unionid TEXT,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                property_id TEXT REFERENCES properties(id) ON DELETE RESTRICT,
                tenant TEXT NOT NULL,
                room TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                monthly_rent INTEGER NOT NULL,
                deposit INTEGER NOT NULL,
                status TEXT NOT NULL,
                days_left INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS maintenance_orders (
                id TEXT PRIMARY KEY,
                property_id TEXT REFERENCES properties(id) ON DELETE RESTRICT,
                title TEXT NOT NULL,
                room TEXT NOT NULL,
                tenant TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                assignee TEXT NOT NULL,
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS finance_transactions (
                id TEXT PRIMARY KEY,
                property_id TEXT REFERENCES properties(id) ON DELETE RESTRICT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                room TEXT NOT NULL,
                tenant TEXT NOT NULL,
                amount INTEGER NOT NULL,
                method TEXT NOT NULL,
                status TEXT NOT NULL,
                note TEXT NOT NULL,
                contract_id TEXT,
                settlement_id TEXT,
                lifecycle_type TEXT
            );

            CREATE TABLE IF NOT EXISTS contract_renewals (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
                property_id TEXT NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
                tenant TEXT NOT NULL,
                room TEXT NOT NULL,
                old_end_date TEXT NOT NULL,
                new_end_date TEXT NOT NULL,
                monthly_rent INTEGER NOT NULL,
                deposit INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS move_outs (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
                property_id TEXT NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
                tenant TEXT NOT NULL,
                room TEXT NOT NULL,
                move_out_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS deposit_settlements (
                id TEXT PRIMARY KEY,
                move_out_id TEXT NOT NULL REFERENCES move_outs(id) ON DELETE RESTRICT,
                contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
                property_id TEXT NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
                tenant TEXT NOT NULL,
                room TEXT NOT NULL,
                deposit INTEGER NOT NULL,
                deductions INTEGER NOT NULL,
                rent_deduction INTEGER NOT NULL DEFAULT 0,
                utility_deduction INTEGER NOT NULL DEFAULT 0,
                damage_deduction INTEGER NOT NULL DEFAULT 0,
                cleaning_deduction INTEGER NOT NULL DEFAULT 0,
                other_deduction INTEGER NOT NULL DEFAULT 0,
                refund_amount INTEGER NOT NULL,
                settled_date TEXT NOT NULL,
                status TEXT NOT NULL,
                method TEXT NOT NULL DEFAULT '银行转账',
                note TEXT NOT NULL DEFAULT '退租押金结算',
                finance_transaction_id TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliation_records (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                bank_flow_id TEXT NOT NULL,
                system_flow_id TEXT NOT NULL,
                payer TEXT NOT NULL,
                amount INTEGER NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                difference INTEGER NOT NULL
            );
            """
        )
        property_columns = {row["name"] for row in db.execute("PRAGMA table_info(properties)").fetchall()}
        related_tables_missing_property_id = any(
            "property_id" not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
            for table in ("tenants", "contracts", "maintenance_orders", "finance_transactions")
        )
        if current_version < 2 or "room_key" not in property_columns or related_tables_missing_property_id:
            _migrate_to_v2(db)
        _migrate_to_v3(db)
        _migrate_to_v4(db)
        _migrate_to_v5(db)
        _migrate_to_v6(db)
        _normalize_legacy_maintenance_orders(db)
        db.execute("CREATE INDEX IF NOT EXISTS idx_login_failures_key_created_at ON login_failures(key, created_at)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_accounts_tenant_id ON tenant_accounts(tenant_id)")
        _ensure_tenant_property_unique_index(db)
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_move_outs_contract_id ON move_outs(contract_id)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_deposit_settlements_move_out_id ON deposit_settlements(move_out_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")
        _install_integrity_triggers(db)

        _validate_schema(db)
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        db.commit()
