import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import FinanceMode, User, UserRole


class UserRepository:
    """get_by_auth0_id/create resolve identity before a TenantContext exists (e.g.
    the Auth0 Action's post-login user-context lookup), so unlike other
    repositories, these methods are not scoped by TenantContext.

    Email is intentionally not handled here yet — CLAUDE.md requires it to be
    Fernet-encrypted at rest (email_encrypted/email_hash), and that encryption
    service lands in Chunk 4.2. Until then, email columns stay NULL.
    """

    async def get_by_auth0_id(self, db: AsyncSession, auth0_user_id: str) -> User | None:
        result = await db.execute(select(User).where(User.auth0_user_id == auth0_user_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await db.get(User, user_id)

    async def create(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        auth0_user_id: str,
        role: UserRole = UserRole.member,
        finance_mode: FinanceMode = FinanceMode.personal,
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            auth0_user_id=auth0_user_id,
            role=role,
            finance_mode=finance_mode,
        )
        db.add(user)
        await db.flush()
        return user

    async def update(self, db: AsyncSession, user: User, **fields: Any) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        await db.flush()
        return user
