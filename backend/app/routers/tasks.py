import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.rbac import role_has_permission
from app.repositories import list_todos
from app.schemas import TodoSeverity, TodoSource, TodoSummary

router = APIRouter(prefix="/tasks", tags=["tasks"])

SOURCE_PERMISSIONS = {
    "contracts": "contracts:view",
    "maintenance": "maintenance:view",
    "finance": "finance:view",
    "reconciliation": "reconciliation:view",
}


@router.get(
    "",
    response_model=TodoSummary,
    dependencies=[Depends(require_permission("tasks:view"))],
)
def get_tasks(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
    source: TodoSource | None = None,
    severity: TodoSeverity | None = None,
) -> TodoSummary:
    allowed_sources = {source for source, permission in SOURCE_PERMISSIONS.items() if role_has_permission(db, current_user["role"], permission)}
    return TodoSummary(**list_todos(db, allowed_sources, limit=limit, offset=offset, q=q, source=source, severity_filter=severity))
