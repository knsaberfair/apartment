import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.repositories import create_tenant as insert_tenant
from app.repositories import delete_tenant as remove_tenant
from app.repositories import list_properties as query_properties
from app.repositories import list_tenants_page as query_tenants_page
from app.repositories import update_tenant as save_tenant
from app.schemas import Property, Tenant, TenantCreate, TenantPage, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


def error_code(exc: KeyError) -> str:
    return exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""


@router.get("", response_model=TenantPage, dependencies=[Depends(require_permission("tenants:view"))])
def list_tenants(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> TenantPage:
    page = query_tenants_page(db, limit=limit, offset=offset, q=q)
    return TenantPage(items=[Tenant(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.get(
    "/property-options",
    response_model=list[Property],
    dependencies=[Depends(require_permission("tenants:view")), Depends(require_permission("properties:view"))],
)
def list_tenant_property_options(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[Property]:
    return [Property(**item) for item in query_properties(db)]


@router.post("", response_model=Tenant, dependencies=[Depends(require_permission("tenants:create"))])
def create_tenant(payload: TenantCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Tenant:
    try:
        return Tenant(**insert_tenant(db, payload.model_dump(), current_user))
    except KeyError as exc:
        code = error_code(exc)
        if code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
            ) from exc
        if code == "TENANT_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_ALREADY_EXISTS", "message": "租客编号已存在"},
            ) from exc
        if code == "PROPERTY_ALREADY_OCCUPIED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_ALREADY_OCCUPIED", "message": "房源不可出租或已被租客占用"},
            ) from exc
        if code == "TENANT_HAS_CONTRACTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_HAS_CONTRACTS", "message": "租客信息与已有合同冲突"},
            ) from exc
        raise


@router.put("/{tenant_id}", response_model=Tenant, dependencies=[Depends(require_permission("tenants:update"))])
def update_tenant(tenant_id: str, payload: TenantUpdate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Tenant:
    try:
        return Tenant(**save_tenant(db, tenant_id, payload.model_dump(), current_user))
    except KeyError as exc:
        code = error_code(exc)
        if code == "TENANT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TENANT_NOT_FOUND", "message": "租客不存在"},
            ) from exc
        if code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
            ) from exc
        if code == "PROPERTY_ALREADY_OCCUPIED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_ALREADY_OCCUPIED", "message": "房源不可出租或已被租客占用"},
            ) from exc
        if code == "TENANT_HAS_CONTRACTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_HAS_CONTRACTS", "message": "租客存在关联合同，不能变更姓名、合同或房源"},
            ) from exc
        if code == "TENANT_HAS_RELATED_RECORDS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_HAS_RELATED_RECORDS", "message": "租客存在工单或财务记录，不能变更姓名、合同或房源"},
            ) from exc
        raise


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("tenants:delete"))])
def delete_tenant(tenant_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Response:
    try:
        remove_tenant(db, tenant_id, current_user)
    except KeyError as exc:
        code = error_code(exc)
        if code == "TENANT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TENANT_NOT_FOUND", "message": "租客不存在"},
            ) from exc
        if code == "TENANT_HAS_RELATED_CONTRACTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_HAS_RELATED_CONTRACTS", "message": "租客存在关联合同，不能删除"},
            ) from exc
        if code == "TENANT_HAS_RELATED_RECORDS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_HAS_RELATED_RECORDS", "message": "租客存在工单或财务记录，不能删除"},
            ) from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
