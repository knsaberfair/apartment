import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import WECHAT_MOCK_LOGIN
from app.database import get_db
from app.dependencies import get_current_tenant
from app.repositories import bind_tenant_account
from app.repositories import create_maintenance_order
from app.repositories import get_tenant_account_by_openid
from app.repositories import get_tenant_account_by_tenant_id
from app.repositories import list_tenant_contracts
from app.repositories import list_tenant_maintenance_orders
from app.repositories import list_tenant_transactions
from app.repositories import pay_tenant_transaction
from app.repositories import touch_tenant_account
from app.schemas import TenantAuthBindRequest, TenantAuthLoginRequest, TenantAuthResponse, TenantBill, TenantContract, TenantHome, TenantProfile, TenantRepair, TenantRepairCreate
from app.security import create_access_token

router = APIRouter(prefix="/tenant", tags=["tenant"])


def _mock_openid(code: str) -> str:
    return f"mock-{hashlib.sha256(code.encode('utf-8')).hexdigest()[:24]}"


def _wechat_openid(code: str) -> str:
    if not WECHAT_MOCK_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"code": "WECHAT_LOGIN_UNAVAILABLE", "message": "微信登录暂未配置"},
        )
    return _mock_openid(code)


def _tenant_token(tenant_id: str) -> str:
    return create_access_token(tenant_id, {"typ": "tenant", "tenant_id": tenant_id})


def _profile(tenant: dict[str, Any]) -> TenantProfile:
    return TenantProfile(**{key: tenant[key] for key in TenantProfile.model_fields})


def _auth_response(db: sqlite3.Connection, tenant_id: str) -> TenantAuthResponse:
    account = touch_tenant_account(db, tenant_id)
    tenant = db.execute(
        """
        SELECT tenant_accounts.id AS account_id,
               tenant_accounts.display_name,
               tenants.*
        FROM tenant_accounts
        JOIN tenants ON tenants.id = tenant_accounts.tenant_id
        WHERE tenants.id = ? AND tenants.status = 'active'
        """,
        (account["tenant_id"],),
    ).fetchone()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TENANT_NOT_BOUND", "message": "租户账号未绑定或已失效"},
        )
    return TenantAuthResponse(access_token=_tenant_token(account["tenant_id"]), profile=_profile(dict(tenant)))


@router.post("/auth/bind", response_model=TenantAuthResponse)
def bind_tenant(payload: TenantAuthBindRequest, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> TenantAuthResponse:
    openid = _wechat_openid(payload.code)
    display_name = payload.display_name.strip()
    try:
        account = bind_tenant_account(db, payload.tenant_id, openid, display_name, payload.unionid)
    except KeyError as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else "TENANT_NOT_BOUND"
        if code == "TENANT_ACCOUNT_ALREADY_BOUND" and WECHAT_MOCK_LOGIN and payload.code == f"tenant-dev-{payload.tenant_id}":
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            with db:
                db.execute(
                    """
                    UPDATE tenant_accounts
                    SET openid = ?, unionid = ?, display_name = ?, last_login_at = ?
                    WHERE tenant_id = ?
                    """,
                    (openid, payload.unionid, display_name, now, payload.tenant_id),
                )
            account = get_tenant_account_by_tenant_id(db, payload.tenant_id)
            if account:
                return _auth_response(db, account["tenant_id"])
        status_code = status.HTTP_409_CONFLICT if code == "TENANT_ACCOUNT_ALREADY_BOUND" else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail={"code": code, "message": "租户账号绑定失败"}) from exc
    return _auth_response(db, account["tenant_id"])


@router.post("/auth/login", response_model=TenantAuthResponse)
def login_tenant(payload: TenantAuthLoginRequest, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> TenantAuthResponse:
    account = get_tenant_account_by_openid(db, _wechat_openid(payload.code))
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TENANT_NOT_BOUND", "message": "租户账号未绑定"},
        )
    return _auth_response(db, account["tenant_id"])


@router.get("/profile", response_model=TenantProfile)
def get_profile(current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> TenantProfile:
    return _profile(current_tenant)


@router.get("/contracts", response_model=list[TenantContract])
def get_contracts(db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> list[TenantContract]:
    return [TenantContract(**item) for item in list_tenant_contracts(db, current_tenant["id"])]


@router.get("/bills", response_model=list[TenantBill])
def get_bills(db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> list[TenantBill]:
    return [TenantBill(**item) for item in list_tenant_transactions(db, current_tenant["id"])]


@router.post("/bills/{bill_id}/pay", response_model=TenantBill)
def pay_bill(bill_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> TenantBill:
    try:
        bill = pay_tenant_transaction(db, current_tenant["id"], bill_id, "微信支付", current_tenant)
    except KeyError as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else "FINANCE_TRANSACTION_NOT_FOUND"
        status_code = status.HTTP_409_CONFLICT if code == "INVALID_FINANCE_STATUS" else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail={"code": code, "message": "账单缴费失败"}) from exc
    return TenantBill(**bill)


@router.get("/repairs", response_model=list[TenantRepair])
def get_repairs(db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> list[TenantRepair]:
    return [TenantRepair(**item) for item in list_tenant_maintenance_orders(db, current_tenant["id"])]


@router.post("/repairs", response_model=TenantRepair)
def create_repair(payload: TenantRepairCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> TenantRepair:
    repair_key = f"{current_tenant['id']}\0{payload.title}\0{payload.due_at}"
    repair_id = f"MT-{hashlib.sha256(repair_key.encode('utf-8')).hexdigest()[:16].upper()}"
    try:
        order = create_maintenance_order(
            db,
            {
                "id": repair_id,
                "property_id": current_tenant["property_id"],
                "title": payload.title,
                "tenant": current_tenant["name"],
                "category": payload.category,
                "priority": payload.priority,
                "due_at": payload.due_at,
            },
            current_tenant,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.args[0], "message": "报修数据不合法"}) from exc
    return TenantRepair(**order)


@router.get("/home", response_model=TenantHome)
def get_home(db: Annotated[sqlite3.Connection, Depends(get_db)], current_tenant: Annotated[dict[str, Any], Depends(get_current_tenant)]) -> TenantHome:
    contracts = [TenantContract(**item) for item in list_tenant_contracts(db, current_tenant["id"])]
    bills = [TenantBill(**item) for item in list_tenant_transactions(db, current_tenant["id"])]
    repairs = [TenantRepair(**item) for item in list_tenant_maintenance_orders(db, current_tenant["id"])]
    return TenantHome(
        profile=_profile(current_tenant),
        contract_count=len(contracts),
        bill_count=len(bills),
        repair_count=len(repairs),
        recent_contracts=contracts[:3],
        recent_bills=bills[:3],
        recent_repairs=repairs[:3],
    )
