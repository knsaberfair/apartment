import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.rbac import (
    create_permission_resource,
    create_role,
    delete_permission_resource,
    delete_role,
    get_permission_catalog,
    list_menu_resources,
    list_permission_resources,
    list_roles,
    update_permission_resource,
    update_role_label,
    update_role_permissions,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])


class CreateRoleRequest(BaseModel):
    key: str
    label: str
    permissions: list[str]


class UpdateRoleRequest(BaseModel):
    label: str


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


class PermissionResourceBaseRequest(BaseModel):
    label: str
    description: str
    group: str
    group_label: str
    type: str
    route: str | None = None
    menu_label: str | None = None
    menu_hint: str | None = None
    sort: int | None = None


class CreatePermissionResourceRequest(PermissionResourceBaseRequest):
    key: str


class UpdatePermissionResourceRequest(PermissionResourceBaseRequest):
    pass


@router.get("/catalog", dependencies=[Depends(require_permission("permissions:view"))])
def get_catalog(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[dict[str, Any]]:
    return get_permission_catalog(db)


@router.get("/resources", dependencies=[Depends(require_permission("permissions:view"))])
def get_resources(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[dict[str, Any]]:
    return list_permission_resources(db)


def _permission_resource_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PERMISSION_NOT_FOUND", "message": "权限资源不存在"},
        )
    if isinstance(exc, PermissionError):
        code = str(exc)
        message = "权限资源正在被角色使用，无法删除" if code == "PERMISSION_RESOURCE_IN_USE" else "内置权限资源不允许修改或删除"
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message})
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "INVALID_PERMISSION_RESOURCE", "message": str(exc)},
    )


@router.post("/resources", dependencies=[Depends(require_permission("permissions:manage"))])
def create_resource(payload: CreatePermissionResourceRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    try:
        return create_permission_resource(db, payload.model_dump(), current_user)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PERMISSION_ALREADY_EXISTS", "message": "权限编码已存在"},
        ) from None
    except ValueError as exc:
        raise _permission_resource_error(exc) from None


@router.put("/resources/{resource_key:path}", dependencies=[Depends(require_permission("permissions:manage"))])
def update_resource(resource_key: str, payload: UpdatePermissionResourceRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    try:
        return update_permission_resource(db, resource_key, payload.model_dump(), current_user)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _permission_resource_error(exc) from None


@router.delete("/resources/{resource_key:path}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("permissions:manage"))])
def remove_resource(resource_key: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> None:
    try:
        delete_permission_resource(db, resource_key, current_user)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _permission_resource_error(exc) from None


@router.get("/menus")
def get_menus(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[dict[str, Any]]:
    return list_menu_resources(db, current_user["role"])


@router.get("/roles", dependencies=[Depends(require_permission("permissions:view"))])
def get_permission_roles(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[dict[str, Any]]:
    return list_roles(db)


@router.post("/roles", dependencies=[Depends(require_permission("permissions:manage"))])
def create_permission_role(payload: CreateRoleRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    try:
        return create_role(db, payload.key, payload.label, set(payload.permissions), current_user)
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


def _role_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_NOT_FOUND", "message": "角色不存在"},
        )
    if isinstance(exc, PermissionError):
        code = str(exc)
        message = "角色正在被用户使用，无法删除" if code == "ROLE_IN_USE" else "内置角色不允许修改或删除"
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message})
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "INVALID_ROLE", "message": str(exc)},
    )


@router.put("/roles/{role}", dependencies=[Depends(require_permission("permissions:manage"))])
def update_role(role: str, payload: UpdateRoleRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    try:
        return update_role_label(db, role, payload.label, current_user)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _role_error(exc) from None


@router.delete("/roles/{role}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("permissions:manage"))])
def remove_role(role: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> None:
    try:
        delete_role(db, role, current_user)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _role_error(exc) from None


@router.put("/roles/{role}/permissions", dependencies=[Depends(require_permission("permissions:manage"))])
def update_permissions(role: str, payload: UpdateRolePermissionsRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    try:
        return update_role_permissions(db, role, set(payload.permissions), current_user)
    except (KeyError, PermissionError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_PERMISSIONS", "message": str(exc)},
            ) from None
        raise _role_error(exc) from None
