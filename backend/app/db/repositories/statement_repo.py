import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.db.models.statement import FileType, Statement, StatementStatus


class StatementRepository:
    async def create(
        self,
        db: AsyncSession,
        ctx: TenantContext,
        *,
        filename: str,
        file_path: str,
        file_type: FileType,
        file_size_bytes: int,
        file_hash: str,
        account_id: uuid.UUID | None = None,
    ) -> Statement:
        statement = Statement(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            account_id=account_id,
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            file_hash=file_hash,
        )
        db.add(statement)
        await db.flush()
        return statement

    async def get_by_id(
        self, db: AsyncSession, ctx: TenantContext, statement_id: uuid.UUID
    ) -> Statement | None:
        result = await db.execute(
            select(Statement).where(
                Statement.id == statement_id,
                Statement.tenant_id == ctx.tenant_id,
                Statement.user_id == ctx.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_worker(self, db: AsyncSession, statement_id: uuid.UUID) -> Statement | None:
        """Unscoped lookup for background tasks. Safe because statement_id is a
        server-generated UUID only ever handed to a task by a request that already
        passed get_tenant_context for that same statement — never attacker input."""
        return await db.get(Statement, statement_id)

    async def get_by_file_hash(
        self, db: AsyncSession, ctx: TenantContext, file_hash: str
    ) -> Statement | None:
        # Tenant-wide, not per-user: two users in the same org shouldn't be able to
        # both ingest the same bank statement file undetected.
        result = await db.execute(
            select(Statement).where(
                Statement.file_hash == file_hash,
                Statement.tenant_id == ctx.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, db: AsyncSession, ctx: TenantContext, *, limit: int = 50, offset: int = 0
    ) -> list[Statement]:
        result = await db.execute(
            select(Statement)
            .where(
                Statement.tenant_id == ctx.tenant_id,
                Statement.user_id == ctx.user_id,
                Statement.deleted_at.is_(None),
            )
            .order_by(Statement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        statement: Statement,
        status: StatementStatus,
        **fields: Any,
    ) -> Statement:
        statement.status = status
        for key, value in fields.items():
            setattr(statement, key, value)
        await db.flush()
        return statement
