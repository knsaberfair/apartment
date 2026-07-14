from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.mock_data import PROPERTIES
from app.schemas import Property

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[Property], dependencies=[Depends(require_permission("properties:view"))])
def list_properties() -> list[Property]:
    return [Property(**item) for item in PROPERTIES]
