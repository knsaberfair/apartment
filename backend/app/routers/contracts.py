from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import CONTRACTS
from app.schemas import Contract

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("", response_model=list[Contract], dependencies=[Depends(require_permission("contracts:view"))])
def list_contracts() -> list[Contract]:
    return [Contract(**item) for item in CONTRACTS]
