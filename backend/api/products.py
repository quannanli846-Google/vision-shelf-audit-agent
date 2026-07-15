from fastapi import APIRouter, Depends

from database.dependencies import get_repository
from database.repository import AuditRepository
from models.db_models import Product

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[Product])
def list_products(repository: AuditRepository = Depends(get_repository)) -> list[Product]:
    """Reference/debug endpoint - lets the frontend or a reviewer inspect the
    grounding catalog directly.
    """
    return repository.list_products()
