from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import MAINTENANCE_ORDERS
from app.schemas import MaintenanceOrder

router = APIRouter(prefix="/maintenance-orders", tags=["maintenance"])


@router.get("", response_model=list[MaintenanceOrder], dependencies=[Depends(require_permission("maintenance:view"))])
def list_maintenance_orders() -> list[MaintenanceOrder]:
    return [MaintenanceOrder(**item) for item in MAINTENANCE_ORDERS]
