import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.repositories import create_property as insert_property
from app.repositories import delete_property as remove_property
from app.repositories import list_properties_page as query_properties_page
from app.repositories import update_property as save_property
from app.schemas import Property, PropertyCreate, PropertyPage, PropertyUpdate

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=PropertyPage, dependencies=[Depends(require_permission("properties:view"))])
def list_properties(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> PropertyPage:
    page = query_properties_page(db, limit=limit, offset=offset, q=q)
    return PropertyPage(items=[Property(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.post("", response_model=Property, dependencies=[Depends(require_permission("properties:create"))])
def create_property(payload: PropertyCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Property:
    try:
        return Property(**insert_property(db, payload.model_dump(), current_user))
    except KeyError as exc:
        error_code = str(exc).strip("'")
        if error_code == "PROPERTY_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_ALREADY_EXISTS", "message": "房源编号已存在"},
            ) from exc
        if error_code == "PROPERTY_ROOM_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_ROOM_ALREADY_EXISTS", "message": "楼栋和房号已存在"},
            ) from exc
        if error_code == "INVALID_PROPERTY_PAYLOAD":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PROPERTY_PAYLOAD", "message": "房源数据不合法"},
            ) from exc
        raise


@router.put("/{property_id}", response_model=Property, dependencies=[Depends(require_permission("properties:update"))])
def update_property(property_id: str, payload: PropertyUpdate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Property:
    try:
        return Property(**save_property(db, property_id, payload.model_dump(), current_user))
    except KeyError as exc:
        error_code = str(exc).strip("'")
        if error_code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
            ) from exc
        if error_code == "PROPERTY_ROOM_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_ROOM_ALREADY_EXISTS", "message": "楼栋和房号已存在"},
            ) from exc
        if error_code == "PROPERTY_HAS_RELATED_RECORDS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_HAS_RELATED_RECORDS", "message": "房源存在租客、合同、工单或财务记录，不能直接变更入住状态、租客、租期、楼栋或房号"},
            ) from exc
        if error_code == "INVALID_PROPERTY_PAYLOAD":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PROPERTY_PAYLOAD", "message": "房源数据不合法"},
            ) from exc
        raise


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("properties:delete"))])
def delete_property(property_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Response:
    try:
        remove_property(db, property_id, current_user)
    except KeyError as exc:
        error_code = str(exc).strip("'")
        if error_code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
            ) from exc
        if error_code == "PROPERTY_HAS_RELATED_RECORDS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PROPERTY_HAS_RELATED_RECORDS", "message": "房源存在租客、合同、工单或财务记录，不能删除"},
            ) from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
