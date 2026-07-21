import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.rbac import role_has_permission
from app.repositories import create_audit_log
from app.repositories import export_dashboard_csv
from app.repositories import get_dashboard_summary as query_dashboard_summary
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SOURCE_PERMISSIONS = {
    "properties": "properties:view",
    "contracts": "contracts:view",
    "maintenance": "maintenance:view",
    "finance": "finance:view",
    "reconciliation": "reconciliation:view",
}


def dashboard_allowed_sources(db: sqlite3.Connection, role: str) -> set[str]:
    return {source for source, permission in SOURCE_PERMISSIONS.items() if role_has_permission(db, role, permission)}


@router.get(
    "/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(require_permission("dashboard:view"))],
)
def get_dashboard_summary(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> DashboardSummary:
    return DashboardSummary(**query_dashboard_summary(db, dashboard_allowed_sources(db, current_user["role"])))


@router.get(
    "/export",
    dependencies=[Depends(require_permission("dashboard:view")), Depends(require_permission("dashboard:export"))],
)
def export_dashboard(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Response:
    content = export_dashboard_csv(db, dashboard_allowed_sources(db, current_user["role"]))
    create_audit_log(db, current_user, "export", "dashboard", "summary")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="dashboard-summary.csv"'},
    )
