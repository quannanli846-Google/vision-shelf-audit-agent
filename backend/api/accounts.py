from fastapi import APIRouter, Depends

from database.dependencies import get_repository
from database.repository import AuditRepository
from models.db_models import Account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[Account])
def list_accounts(repository: AuditRepository = Depends(get_repository)) -> list[Account]:
    return repository.list_accounts()
