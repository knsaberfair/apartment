import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.repositories import assign_maintenance_order as assign_order
from app.repositories import create_maintenance_order as insert_order
from app.repositories import list_maintenance_orders_page as query_maintenance_orders_page
from app.repositories import list_properties as query_properties
from app.repositories import resolve_maintenance_order as resolve_order
from app.schemas import MaintenanceAssignRequest, MaintenanceOrder, MaintenanceOrderCreate, MaintenanceOrderPage, PropertyOption

router = APIRouter(prefix="/maintenance-orders", tags=["maintenance"])


def error_code(exc: KeyError) -> str:
    return exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""


def raise_maintenance_error(exc: KeyError) -> None:
    code = error_code(exc)
    if code == "MAINTENANCE_ORDER_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MAINTENANCE_ORDER_NOT_FOUND", "message": "工单不存在"},
        ) from exc
    if code == "PROPERTY_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROPERTY_NOT_FOUND", "message": "房源不存在"},
        ) from exc
    if code == "MAINTENANCE_ORDER_ALREADY_EXISTS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MAINTENANCE_ORDER_ALREADY_EXISTS", "message": "工单编号已存在"},
        ) from exc
    if code == "INVALID_MAINTENANCE_STATUS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_MAINTENANCE_STATUS", "message": "当前工单状态不支持该操作"},
        ) from exc
    if code == "INVALID_MAINTENANCE_PAYLOAD":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_MAINTENANCE_PAYLOAD", "message": "工单数据不合法"},
        ) from exc
    raise exc


@router.get("", response_model=MaintenanceOrderPage, dependencies=[Depends(require_permission("maintenance:view"))])
def list_maintenance_orders(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> MaintenanceOrderPage:
    page = query_maintenance_orders_page(db, limit=limit, offset=offset, q=q)
    return MaintenanceOrderPage(items=[MaintenanceOrder(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)


@router.get("/property-options", response_model=list[PropertyOption], dependencies=[Depends(require_permission("maintenance:create"))])
def list_maintenance_property_options(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[PropertyOption]:
    return [PropertyOption(**item) for item in query_properties(db)]


@router.post("", response_model=MaintenanceOrder, dependencies=[Depends(require_permission("maintenance:create"))])
def create_maintenance_order(payload: MaintenanceOrderCreate, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> MaintenanceOrder:
    try:
        return MaintenanceOrder(**insert_order(db, payload.model_dump(), current_user))
    except KeyError as exc:
        raise_maintenance_error(exc)


@router.post("/{order_id}/assign", response_model=MaintenanceOrder, dependencies=[Depends(require_permission("maintenance:assign"))])
def assign_maintenance_order(order_id: str, payload: MaintenanceAssignRequest, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> MaintenanceOrder:
    try:
        return MaintenanceOrder(**assign_order(db, order_id, payload.assignee, current_user))
    except KeyError as exc:
        raise_maintenance_error(exc)


@router.post("/{order_id}/resolve", response_model=MaintenanceOrder, dependencies=[Depends(require_permission("maintenance:resolve"))])
def resolve_maintenance_order(order_id: str, db: Annotated[sqlite3.Connection, Depends(get_db)], current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> MaintenanceOrder:
    try:
        return MaintenanceOrder(**resolve_order(db, order_id, current_user))
    except KeyError as exc:
        raise_maintenance_error(exc)
