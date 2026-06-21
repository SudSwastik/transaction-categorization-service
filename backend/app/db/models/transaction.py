import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CategorizationStatus(str, enum.Enum):
    pending = "pending"
    suggested = "suggested"
    confirmed = "confirmed"
    overridden = "overridden"
    skipped = "skipped"


class CategorizationMethod(str, enum.Enum):
    alias = "alias"        # Stage 1 — merchant_aliases match
    pattern = "pattern"    # Stage 2 — user_learning_patterns match
    embedding = "embedding"  # Stage 3 — pgvector similarity
    llm = "llm"            # Stage 4 — Claude classification
    manual = "manual"      # user set directly with no AI suggestion


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )

    # ── Raw extracted fields ──────────────────────────────────────────────────
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_merchant: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # ── Currency & amount ─────────────────────────────────────────────────────
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    raw_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount_base: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    fx_rate_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Categorization ────────────────────────────────────────────────────────
    suggested_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    categorization_status: Mapped[CategorizationStatus] = mapped_column(
        Enum(CategorizationStatus, name="categorization_status"),
        nullable=False,
        default=CategorizationStatus.pending,
        index=True,
    )
    categorization_method: Mapped[CategorizationMethod | None] = mapped_column(
        Enum(CategorizationMethod, name="categorization_method"), nullable=True
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Review ────────────────────────────────────────────────────────────────
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Dedup ─────────────────────────────────────────────────────────────────
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
