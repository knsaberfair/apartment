from collections.abc import Callable
import sqlite3
from typing import Annotated, Any

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import ALLOW_DEMO_ROLE_HEADER, AUTH_COOKIE_NAME
from app.database import get_db
from app.rbac import build_user_response, get_demo_user, role_has_permission
from app.security import decode_access_token, decode_access_token_payload

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    auth_token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_demo_role: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    tokens = [token for token in (credentials.credentials if credentials else None, auth_token) if token]
    for token in tokens:
        payload = decode_access_token_payload(token)
        if not payload or payload.get("typ") == "tenant":
            continue
        username = decode_access_token(token)
        if not username:
            continue
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,),
        ).fetchone()
        if user:
            return build_user_response(db, user)

    if tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效，请重新登录"},
        )

    if ALLOW_DEMO_ROLE_HEADER and x_demo_role:
        return get_demo_user(db, x_demo_role)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "AUTH_REQUIRED", "message": "请先登录"},
    )


def get_current_tenant(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "请先登录租户端"},
        )

    payload = decode_access_token_payload(credentials.credentials)
    if not payload or payload.get("typ") != "tenant":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "租户登录状态无效，请重新登录"},
        )

    tenant_id = payload.get("tenant_id")
    if not isinstance(tenant_id, str) or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "租户登录状态无效，请重新登录"},
        )

    row = db.execute(
        """
        SELECT tenant_accounts.id AS account_id,
               tenant_accounts.tenant_id AS id,
               tenant_accounts.openid,
               tenant_accounts.unionid,
               tenant_accounts.display_name AS account_display_name,
               tenants.name,
               tenants.phone,
               tenants.property_id,
               tenants.room,
               tenants.contract_id,
               tenants.payment_status,
               tenants.move_in_date,
               tenants.lease_end,
               tenants.balance,
               tenants.status,
               tenants.move_out_date
        FROM tenant_accounts
        JOIN tenants ON tenants.id = tenant_accounts.tenant_id
        WHERE tenant_accounts.tenant_id = ?
          AND tenants.status = 'active'
        """,
        (tenant_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TENANT_NOT_BOUND", "message": "租户账号未绑定或已失效"},
        )

    tenant = dict(row)
    tenant["display_name"] = tenant.pop("account_display_name")
    tenant["role"] = "tenant"
    return tenant


def require_permission(permission: str) -> Callable[[sqlite3.Connection, dict[str, Any]], None]:
    def dependency(
        db: Annotated[sqlite3.Connection, Depends(get_db)],
        current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    ) -> None:
        if not role_has_permission(db, current_user["role"], permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "当前角色无权访问该资源",
                    "permission": permission,
                },
            )

    return dependency
