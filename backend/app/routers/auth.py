from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.rbac import list_roles

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_me(current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    return current_user


@router.get("/roles")
def get_roles() -> list[dict[str, Any]]:
    return list_roles()
