from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import RECONCILIATION, TRANSACTIONS
from app.schemas import FinanceTransaction, ReconciliationRecord

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get(
    "/transactions",
    response_model=list[FinanceTransaction],
    dependencies=[Depends(require_permission("finance:view"))],
)
def list_transactions() -> list[FinanceTransaction]:
    return [FinanceTransaction(**item) for item in TRANSACTIONS]


@router.get(
    "/reconciliation",
    response_model=list[ReconciliationRecord],
    dependencies=[Depends(require_permission("reconciliation:view"))],
)
def list_reconciliation_records() -> list[ReconciliationRecord]:
    return [ReconciliationRecord(**item) for item in RECONCILIATION]
