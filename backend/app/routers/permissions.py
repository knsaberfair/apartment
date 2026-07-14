from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import require_permission
from app.rbac import get_permission_catalog, list_roles, update_role_permissions

router = APIRouter(prefix="/permissions", tags=["permissions"])


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


@router.get("/catalog", dependencies=[Depends(require_permission("permissions:view"))])
def get_catalog() -> list[dict]:
    return get_permission_catalog()


@router.get("/roles", dependencies=[Depends(require_permission("permissions:view"))])
def get_permission_roles() -> list[dict]:
    return list_roles()


@router.put("/roles/{role}/permissions", dependencies=[Depends(require_permission("permissions:manage"))])
def update_permissions(role: str, payload: UpdateRolePermissionsRequest) -> dict:
    try:
        return update_role_permissions(role, set(payload.permissions))
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_NOT_FOUND", "message": "角色不存在"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PERMISSIONS", "message": str(exc)},
        ) from None
