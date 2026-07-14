from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import DASHBOARD_SUMMARY
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(require_permission("dashboard:view"))],
)
def get_dashboard_summary() -> DashboardSummary:
    return DashboardSummary(**DASHBOARD_SUMMARY)
