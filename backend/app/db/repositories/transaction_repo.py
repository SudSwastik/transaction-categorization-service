import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction import Transaction


class TransactionRepository:
    async def find_candidates_for_dedup(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        normalized_merchant: str,
        amount: Decimal,
        exclude_statement_id: uuid.UUID,
    ) -> list[Transaction]:
        """Coarse candidate lookup — exact user/merchant/amount match, excluding
        the statement currently being processed (so repeated same-day, same-amount
        transactions within one upload aren't mistaken for duplicates). The ±1 day
        date window is applied by NormalizationAgent._detect_duplicate, which stays
        pure and unit-testable without a database."""
        result = await db.execute(
            select(Transaction).where(
                Transaction.tenant_id == tenant_id,
                Transaction.user_id == user_id,
                Transaction.statement_id != exclude_statement_id,
                Transaction.normalized_merchant == normalized_merchant,
                Transaction.raw_amount == amount,
                Transaction.is_duplicate.is_(False),
                Transaction.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
