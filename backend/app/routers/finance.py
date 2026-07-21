import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.repositories import confirm_transaction as confirm_finance_transaction
from app.repositories import create_audit_log
from app.repositories import create_transaction as insert_transaction
from app.repositories import export_deposit_settlements_csv
from app.repositories import export_reconciliation_csv
from app.repositories import export_transactions_csv
from app.repositories import generate_rent_bills
from app.repositories import import_reconciliation_records as import_records
from app.repositories import list_properties as query_properties
from app.repositories import list_reconciliation_records_page as query_reconciliation_records_page
from app.repositories import list_transactions_page as query_transactions_page
from app.repositories import resolve_reconciliation_record
from app.repositories import retry_reconciliation_record
from app.schemas import FinanceTransaction, FinanceTransactionCreate, FinanceTransactionPage, PropertyOption, ReconciliationImportRequest, ReconciliationRecord, ReconciliationRecordPage, RentBillGenerateRequest, RentBillGenerateResult

router = APIRouter(prefix="/finance", tags=["finance"])


def error_code(exc: KeyError) -> str:
    return exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""


def raise_finance_error(exc: KeyError) -> None:
    code = error_code(exc)
    if code == "PROPERTY_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"}) from exc
    if code == "FINANCE_TRANSACTION_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "FINANCE_TRANSACTION_NOT_FOUND", "message": "财务流水不存在"}) from exc
    if code == "FINANCE_TRANSACTION_ALREADY_EXISTS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "FINANCE_TRANSACTION_ALREADY_EXISTS", "message": "流水编号已存在"}) from exc
    if code == "RESERVED_FINANCE_TRANSACTION_ID":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RESERVED_FINANCE_TRANSACTION_ID", "message": "RENT-/SETTLE-/RENEWAL- 前缀由系统生命周期流水保留"}) from exc
    if code == "INVALID_FINANCE_STATUS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "INVALID_FINANCE_STATUS", "message": "当前财务流水状态不可确认"}) from exc
    if code == "INVALID_FINANCE_PAYLOAD":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_FINANCE_PAYLOAD", "message": "财务流水数据不合法"}) from exc
    if code == "RECONCILIATION_RECORD_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "RECONCILIATION_RECORD_NOT_FOUND", "message": "对账记录不存在"}) from exc
    if code == "RECONCILIATION_RECORD_ALREADY_EXISTS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RECONCILIATION_RECORD_ALREADY_EXISTS", "message": "对账编号已存在"}) from exc
    if code == "RECONCILIATION_FLOW_ALREADY_EXISTS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RECONCILIATION_FLOW_ALREADY_EXISTS", "message": "银行流水或系统流水已对账"}) from exc
    if code == "INVALID_RECONCILIATION_STATUS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "INVALID_RECONCILIATION_STATUS", "message": "当前对账状态不可处理"}) from exc
    if code == "INVALID_RECONCILIATION_PAYLOAD":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_RECONCILIATION_PAYLOAD", "message": "对账流水数据不合法"}) from exc
    raise exc


def csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/transactions",
    response_model=FinanceTransactionPage,
    dependencies=[Depends(require_permission("finance:view"))],
)
def list_transactions(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> FinanceTransactionPage:
    page = query_transactions_page(db, limit=limit, offset=offset, q=q)
    return FinanceTransactionPage(items=[FinanceTransaction(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.get(
    "/transactions/property-options",
    response_model=list[PropertyOption],
    dependencies=[Depends(require_permission("finance:create"))],
)
def list_finance_property_options(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[PropertyOption]:
    return [PropertyOption(**item) for item in query_properties(db)]


@router.post(
    "/transactions",
    response_model=FinanceTransaction,
    dependencies=[Depends(require_permission("finance:create"))],
)
def create_transaction(payload: FinanceTransactionCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> FinanceTransaction:
    if {"contract_id", "settlement_id", "lifecycle_type"} & payload.model_fields_set:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_FINANCE_PAYLOAD", "message": "财务流水数据不合法"})
    try:
        return FinanceTransaction(**insert_transaction(db, payload.model_dump(exclude_unset=True), current_user))
    except KeyError as exc:
        raise_finance_error(exc)


@router.post(
    "/transactions/{transaction_id}/confirm",
    response_model=FinanceTransaction,
    dependencies=[Depends(require_permission("finance:confirm"))],
)
def confirm_transaction(transaction_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> FinanceTransaction:
    try:
        return FinanceTransaction(**confirm_finance_transaction(db, transaction_id, current_user))
    except KeyError as exc:
        raise_finance_error(exc)


@router.get(
    "/transactions/export",
    dependencies=[Depends(require_permission("finance:view")), Depends(require_permission("finance:export"))],
)
def export_transactions(db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Response:
    content = export_transactions_csv(db)
    create_audit_log(db, current_user, "export", "finance_transaction", "all")
    return csv_response(content, "finance-transactions.csv")


@router.post(
    "/rent-bills/generate",
    response_model=RentBillGenerateResult,
    dependencies=[Depends(require_permission("finance:create"))],
)
def generate_rent_bills_endpoint(payload: RentBillGenerateRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> RentBillGenerateResult:
    try:
        result = generate_rent_bills(db, payload.month, current_user)
        return RentBillGenerateResult(
            month=result["month"],
            created=result["created"],
            skipped=result["skipped"],
            transactions=[FinanceTransaction(**item) for item in result["transactions"]],
        )
    except KeyError as exc:
        raise_finance_error(exc)


@router.get(
    "/reconciliation",
    response_model=ReconciliationRecordPage,
    dependencies=[Depends(require_permission("reconciliation:view"))],
)
def list_reconciliation_records(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> ReconciliationRecordPage:
    page = query_reconciliation_records_page(db, limit=limit, offset=offset, q=q)
    return ReconciliationRecordPage(items=[ReconciliationRecord(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.post(
    "/reconciliation/import",
    response_model=list[ReconciliationRecord],
    dependencies=[Depends(require_permission("reconciliation:import"))],
)
def import_reconciliation(payload: ReconciliationImportRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> list[ReconciliationRecord]:
    try:
        return [ReconciliationRecord(**item) for item in import_records(db, [record.model_dump() for record in payload.records], current_user)]
    except KeyError as exc:
        raise_finance_error(exc)


@router.post(
    "/reconciliation/{record_id}/retry-match",
    response_model=ReconciliationRecord,
    dependencies=[Depends(require_permission("reconciliation:resolve"))],
)
def retry_reconciliation(record_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> ReconciliationRecord:
    try:
        return ReconciliationRecord(**retry_reconciliation_record(db, record_id, current_user))
    except KeyError as exc:
        raise_finance_error(exc)


@router.post(
    "/reconciliation/{record_id}/resolve",
    response_model=ReconciliationRecord,
    dependencies=[Depends(require_permission("reconciliation:resolve"))],
)
def resolve_reconciliation(record_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> ReconciliationRecord:
    try:
        return ReconciliationRecord(**resolve_reconciliation_record(db, record_id, current_user))
    except KeyError as exc:
        raise_finance_error(exc)


@router.get(
    "/reconciliation/export",
    dependencies=[Depends(require_permission("reconciliation:view")), Depends(require_permission("reconciliation:export"))],
)
def export_reconciliation(db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Response:
    content = export_reconciliation_csv(db)
    create_audit_log(db, current_user, "export", "reconciliation", "all")
    return csv_response(content, "reconciliation-records.csv")


@router.get(
    "/settlements/export",
    dependencies=[Depends(require_permission("finance:view")), Depends(require_permission("finance:export"))],
)
def export_deposit_settlements(db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Response:
    content = export_deposit_settlements_csv(db)
    create_audit_log(db, current_user, "export", "deposit_settlement", "all")
    return csv_response(content, "deposit-settlements.csv")
