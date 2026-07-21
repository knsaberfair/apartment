import csv
import io

from app.database import get_connection


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_export_dashboard_report(client, admin_token):
    response = client.get("/api/dashboard/export", headers=auth_headers(admin_token))

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "dashboard-summary.csv" in response.headers["content-disposition"]
    assert "occupancy_rate" in response.text
    assert "monthly_income" in response.text
    with get_connection() as db:
        audit_row = db.execute(
            "SELECT 1 FROM audit_logs WHERE action = ? AND resource_type = ? AND resource_id = ?",
            ("export", "dashboard", "summary"),
        ).fetchone()
    assert audit_row is not None


def test_viewer_cannot_export_dashboard_report(client, viewer_token):
    response = client.get("/api/dashboard/export", headers=auth_headers(viewer_token))

    assert response.status_code == 403


def test_dashboard_export_requires_view_permission(client):
    from app.security import hash_password

    with get_connection() as db:
        db.execute("INSERT INTO roles (key, label, built_in) VALUES (?, ?, 0)", ("dashboard_export_only", "只导出控制台"))
        db.execute("INSERT INTO role_permissions (role_key, permission_key) VALUES (?, ?)", ("dashboard_export_only", "dashboard:export"))
        db.execute(
            """
            INSERT INTO users (id, username, display_name, password_hash, role_key, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            ("dashboard-export-only-user", "dashboard_export_only", "只导出控制台", hash_password("dashboard123"), "dashboard_export_only", "2026-07-15T00:00:00+00:00"),
        )
        db.commit()

    token_response = client.post("/api/auth/login", json={"username": "dashboard_export_only", "password": "dashboard123"})
    assert token_response.status_code == 200

    response = client.get("/api/dashboard/export", headers=auth_headers(token_response.json()["access_token"]))

    assert response.status_code == 403


def test_dashboard_summary_uses_real_metrics(client, admin_token):
    response = client.get("/api/dashboard/summary", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    metrics = {item["label"]: item for item in body["metrics"]}
    assert metrics["房源总数"]["value"] == "8"
    assert metrics["出租率"]["value"] == "62%"
    assert metrics["本月收入"]["value"] == "¥19,600"
    assert body["monthly_income"] == 19600
    assert body["pending_tasks"] > 0
    assert len(body["income_trend"]) == 6
    assert body["recent_contracts"][0]["start_date"] >= body["recent_contracts"][-1]["start_date"]


def test_dashboard_summary_hides_sources_without_module_permissions(client):
    maintenance_token_response = client.post("/api/auth/login", json={"username": "maintenance", "password": "maintenance123"})
    assert maintenance_token_response.status_code == 200
    leasing_token_response = client.post("/api/auth/login", json={"username": "leasing", "password": "leasing123"})
    assert leasing_token_response.status_code == 200

    maintenance_response = client.get("/api/dashboard/summary", headers=auth_headers(maintenance_token_response.json()["access_token"]))
    leasing_response = client.get("/api/dashboard/summary", headers=auth_headers(leasing_token_response.json()["access_token"]))

    assert maintenance_response.status_code == 200
    maintenance_body = maintenance_response.json()
    assert maintenance_body["monthly_income"] == 0
    assert all(item["income"] == 0 for item in maintenance_body["income_trend"])
    assert maintenance_body["recent_contracts"] == []
    assert maintenance_body["expiring_contracts"] == 0
    assert maintenance_body["urgent_work_orders"]

    assert leasing_response.status_code == 200
    leasing_body = leasing_response.json()
    assert leasing_body["monthly_income"] == 0
    assert all(item["income"] == 0 for item in leasing_body["income_trend"])
    assert leasing_body["recent_contracts"]
    assert leasing_body["urgent_work_orders"] == []


def test_dashboard_income_trend_counts_paid_and_reconciled_transactions(client, admin_token):
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-DASHBOARD-PAID", "P-1201", "2026-07-16", "租金收入", "A-1201", "林思远", 2000, "银行转账", "paid", "测试收入"),
        )
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-DASHBOARD-PENDING", "P-1201", "2026-07-16", "租金账单", "A-1201", "林思远", 3000, "待收款", "pending", "待收账单"),
        )
        db.commit()

    response = client.get("/api/dashboard/summary", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_income"] == 21600
    july = next(item for item in body["income_trend"] if item["month"] == "07月")
    assert july["income"] == 21600
    assert any(metric["label"] == "待办事项" and int(metric["value"]) >= 1 for metric in body["metrics"])


def test_dashboard_export_escapes_formula_cells(client, admin_token):
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO finance_transactions (id, property_id, date, type, room, tenant, amount, method, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("F-DASHBOARD-FORMULA", "P-1201", "2026-07-16", "租金收入", "A-1201", "林思远", 1, "银行转账", "paid", "测试"),
        )
        db.commit()

    response = client.get("/api/dashboard/export", headers=auth_headers(admin_token))

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    metric = next(row for row in rows if row["label"] == "本月收入")
    assert metric["value"].startswith("'¥") is False
