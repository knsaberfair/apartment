from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import TENANTS
from app.schemas import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("", response_model=list[Tenant], dependencies=[Depends(require_permission("tenants:view"))])
def list_tenants() -> list[Tenant]:
    return [Tenant(**item) for item in TENANTS]
