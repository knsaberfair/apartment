import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.repositories import approve_contract as approve_contract_record
from app.repositories import create_contract as insert_contract
from app.repositories import create_move_out as create_move_out_record
from app.repositories import list_contracts_page as query_contracts_page
from app.repositories import list_contract_renewals as query_contract_renewals
from app.repositories import list_deposit_settlements as query_deposit_settlements
from app.repositories import list_move_outs as query_move_outs
from app.repositories import renew_contract as renew_contract_record
from app.repositories import settle_deposit as settle_deposit_record
from app.repositories import list_properties as query_properties
from app.repositories import terminate_contract as terminate_contract_record
from app.repositories import update_pending_contract as save_pending_contract
from app.schemas import Contract, ContractCreate, ContractPage, ContractRenewal, ContractRenewalRequest, ContractUpdatePending, DepositSettlement, DepositSettlementRequest, MoveOut, MoveOutRequest, Property

router = APIRouter(prefix="/contracts", tags=["contracts"])


def error_code(exc: KeyError) -> str:
    return exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""


def raise_contract_error(exc: KeyError) -> None:
    code = error_code(exc)
    if code == "CONTRACT_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONTRACT_NOT_FOUND", "message": "合同不存在"},
        ) from exc
    if code == "PROPERTY_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
        ) from exc
    if code == "CONTRACT_ALREADY_EXISTS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONTRACT_ALREADY_EXISTS", "message": "合同编号已存在"},
        ) from exc
    if code == "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONTRACT_ALREADY_EXISTS_FOR_PROPERTY", "message": "房源已存在有效合同"},
        ) from exc
    if code == "TENANT_HAS_RELATED_CONTRACTS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TENANT_HAS_RELATED_CONTRACTS", "message": "租客存在关联合同，不能直接终止"},
        ) from exc
    if code == "TENANT_HAS_CONTRACTS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TENANT_HAS_CONTRACTS", "message": "租客信息与已有合同冲突"},
        ) from exc
    if code == "INVALID_CONTRACT_STATUS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_CONTRACT_STATUS", "message": "当前合同状态不支持该操作"},
        ) from exc
    if code == "INVALID_CONTRACT_PAYLOAD":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CONTRACT_PAYLOAD", "message": "合同数据不合法"},
        ) from exc
    if code == "CONTRACT_DELETE_FORBIDDEN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONTRACT_DELETE_FORBIDDEN", "message": "合同历史不能删除"},
        ) from exc
    if code in {"MOVE_OUT_ALREADY_EXISTS", "SETTLEMENT_ALREADY_EXISTS"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": code, "message": "生命周期记录已存在"},
        ) from exc
    if code == "MOVE_OUT_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MOVE_OUT_NOT_FOUND", "message": "退租记录不存在"},
        ) from exc
    if code in {"INVALID_MOVE_OUT_PAYLOAD", "INVALID_SETTLEMENT_PAYLOAD"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": code, "message": "生命周期数据不合法"},
        ) from exc
    if code == "PROPERTY_HAS_RELATED_RECORDS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PROPERTY_HAS_RELATED_RECORDS", "message": "房源存在关联记录，不能同步合同状态"},
        ) from exc
    raise exc


@router.get("", response_model=ContractPage, dependencies=[Depends(require_permission("contracts:view"))])
def list_contracts(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> ContractPage:
    page = query_contracts_page(db, limit=limit, offset=offset, q=q)
    return ContractPage(items=[Contract(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.get("/property-options", response_model=list[Property], dependencies=[Depends(require_permission("contracts:create"))])
def list_contract_property_options(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[Property]:
    return [Property(**item) for item in query_properties(db)]


@router.post("", response_model=Contract, dependencies=[Depends(require_permission("contracts:create"))])
def create_contract(payload: ContractCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Contract:
    try:
        return Contract(**insert_contract(db, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.put("/{contract_id}", response_model=Contract, dependencies=[Depends(require_permission("contracts:create"))])
def update_contract(contract_id: str, payload: ContractUpdatePending, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Contract:
    try:
        return Contract(**save_pending_contract(db, contract_id, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.post("/{contract_id}/approve", response_model=Contract, dependencies=[Depends(require_permission("contracts:approve"))])
def approve_contract(contract_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Contract:
    try:
        return Contract(**approve_contract_record(db, contract_id, current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.post("/{contract_id}/terminate", response_model=Contract, dependencies=[Depends(require_permission("contracts:terminate"))])
def terminate_contract(contract_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Contract:
    try:
        return Contract(**terminate_contract_record(db, contract_id, current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.get("/{contract_id}/renewals", response_model=list[ContractRenewal], dependencies=[Depends(require_permission("contracts:view"))])
def list_renewals(contract_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[ContractRenewal]:
    return [ContractRenewal(**item) for item in query_contract_renewals(db, contract_id)]


@router.post("/{contract_id}/renew", response_model=ContractRenewal, dependencies=[Depends(require_permission("contracts:approve"))])
def renew_contract(contract_id: str, payload: ContractRenewalRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> ContractRenewal:
    try:
        return ContractRenewal(**renew_contract_record(db, contract_id, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.get("/{contract_id}/move-outs", response_model=list[MoveOut], dependencies=[Depends(require_permission("contracts:view"))])
def list_contract_move_outs(contract_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[MoveOut]:
    return [MoveOut(**item) for item in query_move_outs(db, contract_id)]


@router.post("/{contract_id}/move-out", response_model=MoveOut, dependencies=[Depends(require_permission("contracts:terminate"))])
def move_out_contract(contract_id: str, payload: MoveOutRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> MoveOut:
    try:
        return MoveOut(**create_move_out_record(db, contract_id, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_contract_error(exc)


@router.get("/move-outs/{move_out_id}/settlements", response_model=list[DepositSettlement], dependencies=[Depends(require_permission("contracts:view")), Depends(require_permission("finance:view"))])
def list_move_out_settlements(move_out_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[DepositSettlement]:
    return [DepositSettlement(**item) for item in query_deposit_settlements(db, move_out_id)]


@router.post("/move-outs/{move_out_id}/settle", response_model=DepositSettlement, dependencies=[Depends(require_permission("contracts:terminate")), Depends(require_permission("finance:confirm"))])
def settle_move_out(move_out_id: str, payload: DepositSettlementRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> DepositSettlement:
    try:
        return DepositSettlement(**settle_deposit_record(db, move_out_id, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_contract_error(exc)
