import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.dependencies import require_permission
from app.repositories import list_audit_logs_page as query_audit_logs_page
from app.schemas import AuditLog, AuditLogPage

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _validate_datetime_filter(value: str | None, field_name: str) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"field": field_name, "message": "must be a valid ISO datetime"}) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HTTPException(status_code=422, detail={"field": field_name, "message": "must include timezone"})
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


@router.get("", response_model=AuditLogPage, dependencies=[Depends(require_permission("audit:view"))])
def list_audit_logs(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
    actor_id: Annotated[str | None, Query(max_length=100)] = None,
    actor_role: Annotated[str | None, Query(max_length=50)] = None,
    action: Annotated[str | None, Query(max_length=50)] = None,
    resource_type: Annotated[str | None, Query(max_length=100)] = None,
    resource_id: Annotated[str | None, Query(max_length=100)] = None,
    created_from: Annotated[str | None, Query(max_length=40)] = None,
    created_to: Annotated[str | None, Query(max_length=40)] = None,
) -> AuditLogPage:
    created_from = _validate_datetime_filter(created_from, "created_from")
    created_to = _validate_datetime_filter(created_to, "created_to")
    if created_from and created_to and datetime.fromisoformat(created_from) > datetime.fromisoformat(created_to):
        raise HTTPException(status_code=422, detail={"field": "created_to", "message": "must be greater than or equal to created_from"})

    page = query_audit_logs_page(
        db,
        limit=limit,
        offset=offset,
        q=q,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        created_from=created_from,
        created_to=created_to,
    )
    return AuditLogPage(items=[AuditLog(**item) for item in page["items"]], total=page["total"], limit=limit, offset=offset)
