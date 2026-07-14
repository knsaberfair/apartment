from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import require_permission
from app.rbac import (
    create_permission_resource,
    create_role,
    get_permission_catalog,
    list_menu_resources,
    list_permission_resources,
    list_roles,
    update_role_permissions,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])


class CreateRoleRequest(BaseModel):
    key: str
    label: str
    permissions: list[str]


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


class CreatePermissionResourceRequest(BaseModel):
    key: str
    label: str
    description: str
    group: str
    group_label: str
    type: str
    route: str | None = None
    menu_label: str | None = None
    menu_hint: str | None = None
    sort: int | None = None


@router.get("/catalog", dependencies=[Depends(require_permission("permissions:view"))])
def get_catalog() -> list[dict[str, Any]]:
    return get_permission_catalog()


@router.get("/resources", dependencies=[Depends(require_permission("permissions:view"))])
def get_resources() -> list[dict[str, Any]]:
    return list_permission_resources()


@router.post("/resources", dependencies=[Depends(require_permission("permissions:manage"))])
def create_resource(payload: CreatePermissionResourceRequest) -> dict[str, Any]:
    try:
        return create_permission_resource(payload.model_dump())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PERMISSION_ALREADY_EXISTS", "message": "权限编码已存在"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PERMISSION_RESOURCE", "message": str(exc)},
        ) from None


@router.get("/menus")
def get_menus() -> list[dict[str, Any]]:
    return list_menu_resources()


@router.get("/roles", dependencies=[Depends(require_permission("permissions:view"))])
def get_permission_roles() -> list[dict[str, Any]]:
    return list_roles()


@router.post("/roles", dependencies=[Depends(require_permission("permissions:manage"))])
def create_permission_role(payload: CreateRoleRequest) -> dict[str, Any]:
    try:
        return create_role(payload.key, payload.label, set(payload.permissions))
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ROLE_ALREADY_EXISTS", "message": "角色编码已存在"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ROLE", "message": str(exc)},
        ) from None


@router.put("/roles/{role}/permissions", dependencies=[Depends(require_permission("permissions:manage"))])
def update_permissions(role: str, payload: UpdateRolePermissionsRequest) -> dict[str, Any]:
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
