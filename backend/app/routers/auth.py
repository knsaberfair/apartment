import sqlite3
from time import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.config import APP_ENV, AUTH_COOKIE_MAX_AGE_SECONDS, AUTH_COOKIE_NAME, AUTH_COOKIE_PATH, AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE, ENABLE_DEMO_SEED
from app.database import get_db
from app.dependencies import get_current_user
from app.rbac import build_user_response, list_roles
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_FAILURE_WINDOW_SECONDS = 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURES_MAX_ROWS = 1000


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class DemoLoginRequest(BaseModel):
    role: str


DEMO_ROLE_USERS = {
    "super_admin": "admin",
    "manager": "manager",
    "leasing_agent": "leasing",
    "maintenance_staff": "maintenance",
    "finance_staff": "finance",
    "viewer": "viewer",
}


def _login_key(username: str) -> str:
    return username.strip().lower()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _throttle_keys(username: str, request: Request) -> tuple[str, str]:
    client = _client_key(request)
    return f"username:{_login_key(username)}", f"client:{client}"


def _prune_login_failures(db: sqlite3.Connection, now: float) -> None:
    db.execute("DELETE FROM login_failures WHERE created_at < ?", (now - LOGIN_FAILURE_WINDOW_SECONDS,))
    extra_rows = db.execute("SELECT COUNT(*) AS count FROM login_failures").fetchone()["count"] - LOGIN_FAILURES_MAX_ROWS
    if extra_rows > 0:
        db.execute("DELETE FROM login_failures WHERE id IN (SELECT id FROM login_failures ORDER BY created_at LIMIT ?)", (extra_rows,))


def _too_many_login_attempts() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "TOO_MANY_LOGIN_ATTEMPTS", "message": "登录尝试过多，请稍后再试"},
    )


def _failure_count(db: sqlite3.Connection, keys: tuple[str, ...]) -> int:
    row = db.execute(
        f"SELECT COUNT(*) AS count FROM login_failures WHERE key IN ({', '.join('?' for _ in keys)}) GROUP BY key ORDER BY count DESC LIMIT 1",
        keys,
    ).fetchone()
    return row["count"] if row else 0


def _assert_login_allowed(db: sqlite3.Connection, keys: tuple[str, ...]) -> None:
    now = time()
    with db:
        _prune_login_failures(db, now)
        failure_count = _failure_count(db, keys)
    if failure_count >= LOGIN_FAILURE_LIMIT:
        raise _too_many_login_attempts()


def _record_login_failure(db: sqlite3.Connection, keys: tuple[str, ...]) -> None:
    now = time()
    with db:
        db.execute("BEGIN IMMEDIATE")
        _prune_login_failures(db, now)
        db.executemany("INSERT INTO login_failures (key, created_at) VALUES (?, ?)", [(key, now) for key in keys])
        failure_count = _failure_count(db, keys)
    if failure_count > LOGIN_FAILURE_LIMIT:
        raise _too_many_login_attempts()


def _clear_login_failures(db: sqlite3.Connection, keys: tuple[str, ...]) -> None:
    with db:
        db.execute(f"DELETE FROM login_failures WHERE key IN ({', '.join('?' for _ in keys)})", keys)


def _build_login_response(db: sqlite3.Connection, user: sqlite3.Row, token: str) -> dict[str, Any]:
    return {"access_token": token, "token_type": "bearer", "user": build_user_response(db, user)}


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        path=AUTH_COOKIE_PATH,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path=AUTH_COOKIE_PATH)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> dict[str, Any]:
    username = payload.username.strip()
    throttle_keys = _throttle_keys(username, request)
    _assert_login_allowed(db, throttle_keys)

    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,),
    ).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        _record_login_failure(db, throttle_keys)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码错误"},
        )

    _clear_login_failures(db, (throttle_keys[0],))
    token = create_access_token(user["username"])
    _set_auth_cookie(response, token)
    return _build_login_response(db, user, token)


@router.post("/demo-login")
def demo_login(payload: DemoLoginRequest, response: Response, db: Annotated[sqlite3.Connection, Depends(get_db)]) -> dict[str, Any]:
    if APP_ENV not in {"development", "test"} or not ENABLE_DEMO_SEED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "演示登录不可用"},
        )

    username = DEMO_ROLE_USERS.get(payload.role)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DEMO_ROLE", "message": "演示角色不存在"},
        )

    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,),
    ).fetchone()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEMO_USER_NOT_FOUND", "message": "演示账号未初始化"},
        )

    token = create_access_token(user["username"])
    _set_auth_cookie(response, token)
    return _build_login_response(db, user, token)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    _clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/me")
def get_me(current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    return current_user


@router.get("/roles")
def get_roles(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    _current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[dict[str, Any]]:
    return [{"key": role["key"], "label": role["label"], "permissions": []} for role in list_roles(db)]
