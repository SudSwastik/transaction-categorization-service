import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import Base


class LtreeType(UserDefinedType):
    """Maps to PostgreSQL ltree extension type."""

    cache_ok = True

    def get_col_spec(self) -> str:
        return "LTREE"


class FinanceType(str, enum.Enum):
    personal = "personal"
    business = "business"
    both = "both"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NULL for system categories, set for tenant-owned custom categories
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    finance_type: Mapped[FinanceType] = mapped_column(
        Enum(FinanceType, name="finance_type"), nullable=False, default=FinanceType.personal
    )

    # ltree path — e.g. "food_dining.restaurants" — enables fast ancestor/descendant queries
    path: Mapped[str | None] = mapped_column(LtreeType, nullable=True)

    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Optional UI hints
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)   # hex e.g. "#FF5733"
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)   # icon name/slug

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
