import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentType(str, enum.Enum):
    statement = "statement"
    normalization = "normalization"
    categorization = "categorization"
    learning = "learning"


class AgentRunStatus(str, enum.Enum):
    started = "started"
    completed = "completed"
    failed = "failed"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    agent_type: Mapped[AgentType] = mapped_column(
        Enum(AgentType, name="agent_type"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name="agent_run_status"), nullable=False, default=AgentRunStatus.started
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # LLM reasoning stored here, not on transactions
    llm_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
