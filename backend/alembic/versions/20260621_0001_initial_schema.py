"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-21 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    # ── Enums ─────────────────────────────────────────────────────────────────
    user_role = postgresql.ENUM("owner", "admin", "member", "viewer", name="user_role")
    finance_mode = postgresql.ENUM("personal", "business", "both", name="finance_mode")
    account_type = postgresql.ENUM("checking", "savings", "credit", "business", name="account_type")
    file_type = postgresql.ENUM("pdf", "xlsx", "docx", "jpg", "jpeg", "png", name="file_type")
    statement_status = postgresql.ENUM(
        "uploaded", "parsing", "parsed", "normalizing",
        "categorizing", "pending_review", "completed", "failed",
        name="statement_status",
    )
    categorization_status = postgresql.ENUM(
        "pending", "suggested", "confirmed", "overridden", "skipped",
        name="categorization_status",
    )
    categorization_method = postgresql.ENUM(
        "alias", "pattern", "embedding", "llm", "manual",
        name="categorization_method",
    )
    finance_type = postgresql.ENUM("personal", "business", "both", name="finance_type")
    match_type = postgresql.ENUM("exact", "prefix", "contains", "regex", name="match_type")
    feedback_event_type = postgresql.ENUM(
        "approved", "corrected", "skipped", name="feedback_event_type"
    )
    agent_type = postgresql.ENUM(
        "statement", "normalization", "categorization", "learning", name="agent_type"
    )
    agent_run_status = postgresql.ENUM(
        "started", "completed", "failed", name="agent_run_status"
    )
    job_type = postgresql.ENUM(
        "parse_statement", "extract_transactions",
        "normalize_transactions", "categorize_transactions",
        name="job_type",
    )
    job_status = postgresql.ENUM("queued", "running", "completed", "failed", name="job_status")

    for enum in [
        user_role, finance_mode, account_type, file_type, statement_status,
        categorization_status, categorization_method, finance_type, match_type,
        feedback_event_type, agent_type, agent_run_status, job_type, job_status,
    ]:
        enum.create(op.get_bind(), checkfirst=True)

    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("auth0_org_id", sa.String(255), nullable=True),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auth0_user_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("email_hash", sa.String(64), nullable=True),
        sa.Column("role", postgresql.ENUM("owner", "admin", "member", "viewer", name="user_role", create_type=False), nullable=False, server_default="member"),
        sa.Column("finance_mode", postgresql.ENUM("personal", "business", "both", name="finance_mode", create_type=False), nullable=False, server_default="personal"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_auth0_user_id", "users", ["auth0_user_id"])
    op.create_index("ix_users_email_hash", "users", ["email_hash"])

    # ── accounts ──────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_name", sa.String(255), nullable=False),
        sa.Column("account_type", postgresql.ENUM("checking", "savings", "credit", "business", name="account_type", create_type=False), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_accounts_tenant_id", "accounts", ["tenant_id"])
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("finance_type", postgresql.ENUM("personal", "business", "both", name="finance_type", create_type=False), nullable=False, server_default="personal"),
        sa.Column("path", sa.Text, nullable=True),  # stored as ltree
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_categories_tenant_id", "categories", ["tenant_id"])
    # Cast path column to LTREE after table creation
    op.execute("ALTER TABLE categories ALTER COLUMN path TYPE LTREE USING path::LTREE")
    op.execute("CREATE INDEX ix_categories_path ON categories USING GIST (path)")

    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", postgresql.ENUM("parse_statement", "extract_transactions", "normalize_transactions", "categorize_transactions", name="job_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("queued", "running", "completed", "failed", name="job_status", create_type=False), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_entity_id", "jobs", ["entity_id"])

    # ── statements ────────────────────────────────────────────────────────────
    op.create_table(
        "statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_type", postgresql.ENUM("pdf", "xlsx", "docx", "jpg", "jpeg", "png", name="file_type", create_type=False), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("file_hash", sa.String(71), nullable=False),
        sa.Column("status", postgresql.ENUM("uploaded", "parsing", "parsed", "normalizing", "categorizing", "pending_review", "completed", "failed", name="statement_status", create_type=False), nullable=False, server_default="uploaded"),
        sa.Column("transaction_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_statements_tenant_id", "statements", ["tenant_id"])
    op.create_index("ix_statements_user_id", "statements", ["user_id"])
    op.create_index("ix_statements_file_hash", "statements", ["file_hash"])
    op.create_index("ix_statements_status", "statements", ["status"])

    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raw_description", sa.Text, nullable=False),
        sa.Column("normalized_merchant", sa.String(255), nullable=True),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("source_currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("raw_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount_base", sa.Numeric(18, 4), nullable=True),
        sa.Column("fx_rate_used", sa.Numeric(18, 8), nullable=True),
        sa.Column("fx_rate_date", sa.Date, nullable=True),
        sa.Column("suggested_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("categorization_status", postgresql.ENUM("pending", "suggested", "confirmed", "overridden", "skipped", name="categorization_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("categorization_method", postgresql.ENUM("alias", "pattern", "embedding", "llm", "manual", name="categorization_method", create_type=False), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence_breakdown", postgresql.JSONB, nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_tenant_id", "transactions", ["tenant_id"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_statement_id", "transactions", ["statement_id"])
    op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_normalized_merchant", "transactions", ["normalized_merchant"])
    op.create_index("ix_transactions_categorization_status", "transactions", ["categorization_status"])
    op.create_index("ix_transactions_is_duplicate", "transactions", ["is_duplicate"])

    # ── merchant_aliases ──────────────────────────────────────────────────────
    op.create_table(
        "merchant_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_pattern", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("match_type", postgresql.ENUM("exact", "prefix", "contains", "regex", name="match_type", create_type=False), nullable=False, server_default="exact"),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_merchant_aliases_tenant_id", "merchant_aliases", ["tenant_id"])
    op.create_index("ix_merchant_aliases_user_id", "merchant_aliases", ["user_id"])

    # ── user_learning_patterns ────────────────────────────────────────────────
    op.create_table(
        "user_learning_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_key", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0.5"),
        sa.Column("match_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ulp_tenant_id", "user_learning_patterns", ["tenant_id"])
    op.create_index("ix_ulp_user_id", "user_learning_patterns", ["user_id"])
    op.create_index("ix_ulp_pattern_key", "user_learning_patterns", ["pattern_key"])

    # ── transaction_embeddings ────────────────────────────────────────────────
    op.create_table(
        "transaction_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transaction_embeddings_tenant_id", "transaction_embeddings", ["tenant_id"])
    op.create_index("ix_transaction_embeddings_user_id", "transaction_embeddings", ["user_id"])
    op.execute(
        "CREATE INDEX ix_transaction_embeddings_hnsw ON transaction_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── category_embeddings ───────────────────────────────────────────────────
    op.create_table(
        "category_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_category_embeddings_tenant_id", "category_embeddings", ["tenant_id"])
    op.execute(
        "CREATE INDEX ix_category_embeddings_hnsw ON category_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── feedback_events ───────────────────────────────────────────────────────
    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", postgresql.ENUM("approved", "corrected", "skipped", name="feedback_event_type", create_type=False), nullable=False),
        sa.Column("original_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("corrected_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_events_tenant_id", "feedback_events", ["tenant_id"])
    op.create_index("ix_feedback_events_user_id", "feedback_events", ["user_id"])
    op.create_index("ix_feedback_events_transaction_id", "feedback_events", ["transaction_id"])

    # ── agent_runs ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_type", postgresql.ENUM("statement", "normalization", "categorization", "learning", name="agent_type", create_type=False), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", postgresql.ENUM("started", "completed", "failed", name="agent_run_status", create_type=False), nullable=False, server_default="started"),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("llm_reasoning", sa.Text, nullable=True),
        sa.Column("input_metadata", postgresql.JSONB, nullable=True),
        sa.Column("output_metadata", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"])
    op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"])
    op.create_index("ix_agent_runs_entity_id", "agent_runs", ["entity_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field_changes", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_runs")
    op.drop_table("feedback_events")
    op.drop_table("category_embeddings")
    op.drop_table("transaction_embeddings")
    op.drop_table("user_learning_patterns")
    op.drop_table("merchant_aliases")
    op.drop_table("transactions")
    op.drop_table("statements")
    op.drop_table("jobs")
    op.drop_table("categories")
    op.drop_table("accounts")
    op.drop_table("users")
    op.drop_table("tenants")

    for name in [
        "user_role", "finance_mode", "account_type", "file_type",
        "statement_status", "categorization_status", "categorization_method",
        "finance_type", "match_type", "feedback_event_type",
        "agent_type", "agent_run_status", "job_type", "job_status",
    ]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)

    op.execute("DROP EXTENSION IF EXISTS ltree")
    op.execute("DROP EXTENSION IF EXISTS vector")
