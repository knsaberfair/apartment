from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from app.rbac import get_demo_user, normalize_role, role_has_permission


def get_current_role(x_demo_role: Annotated[str | None, Header()] = None) -> str:
    return normalize_role(x_demo_role)


def get_current_user(role: Annotated[str, Depends(get_current_role)]) -> dict[str, Any]:
    return get_demo_user(role)


def require_permission(permission: str) -> Callable[[str], None]:
    def dependency(role: Annotated[str, Depends(get_current_role)]) -> None:
        if not role_has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "当前角色无权访问该资源",
                    "permission": permission,
                },
            )

    return dependency
