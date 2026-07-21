from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context
from app.core.context import TenantContext
from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.db.repositories.user_repo import UserRepository
from app.schemas.auth import CurrentUserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_user_repo = UserRepository()


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> CurrentUserResponse:
    user = await _user_repo.get_by_id(db, ctx.user_id)
    if user is None or user.tenant_id != ctx.tenant_id:
        # JWT claims validated fine, but the user they point to doesn't match our
        # DB state (deleted, moved tenants, stale Action cache) — 404, not 403.
        raise NotFoundError("User not found")

    return CurrentUserResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=None,  # email encryption lands in Chunk 4.2
        role=user.role,
    )
