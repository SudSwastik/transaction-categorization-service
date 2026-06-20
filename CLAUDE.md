# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Multi-tenant SaaS platform that ingests financial statements (PDF, XLSX, DOCX, images), extracts transactions, categorizes them via a 5-stage AI pipeline, and learns from per-user feedback. Full architecture decisions are in `IMPLEMENTATION_PLAN.md`.

---

## Commands

> Commands will be populated as each phase is implemented. The expected final commands are listed here for reference.

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload          # dev server
uv run pytest tests/unit/ -v                  # unit tests
uv run pytest tests/integration/ -v           # integration tests (requires docker compose up)
uv run pytest tests/ -k "test_dedup"          # single test by name
uv run ruff check .                           # lint
uv run mypy app/                              # type check
alembic upgrade head                          # apply migrations
alembic revision --autogenerate -m "<msg>"    # generate migration after model change

# Workers
celery -A app.tasks.celery_app worker -Q default -c 4 --loglevel=info
celery -A app.tasks.celery_app worker -Q llm -c 2 --loglevel=info

# Full stack
docker compose up -d                          # start all services
docker compose restart backend celery-worker-default  # after code change
docker compose down                           # stop (keeps volumes)
docker compose down -v                        # DANGER: also deletes uploads volume + postgres data

# Seeding
python scripts/seed_categories.py             # seed built-in category taxonomy
python scripts/create_tenant.py              # create a tenant + owner user
```

---

## Stack Decisions (with reasoning)

| Concern | Choice | Why |
|---|---|---|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim) | Claude has no embeddings API; local model means zero per-call cost and transaction descriptions never leave the server |
| LLM | Anthropic `claude-sonnet-4-6` | Used only for Stage 4 classification, not embeddings |
| Vector DB | pgvector on PostgreSQL (HNSW index) | Single DB for relational + vectors; 384 dims is well within pgvector's performance range at this scale |
| Queue | Celery + Redis with 4 named queues | `llm` queue is rate-limited separately (10 calls/min per tenant); `learning` queue runs async after user feedback |
| Auth | Auth0 free tier + custom post-login Action | Auth0 Organizations (paid) not needed — we manage tenants ourselves; Action injects `tenant_id`, `user_id`, `role` into JWT |
| File storage | Docker named volume (`uploads`) via `StorageService` abstraction | Self-hosted Docker Compose; `STORAGE_BACKEND=s3` env var switches to S3 with no code changes |

---

## Non-Negotiable Architecture Rules

These are explicit product decisions — do not change them without discussion.

### 1. Always require user confirmation
There is **no auto-approve path**. The AI always suggests; the user always approves or corrects. `categorization_status` must pass through `suggested` before it can become `confirmed`. Do not add any code path that sets `confirmed_category_id` without a user action.

### 2. Learning is per-user only — never cross-user or cross-tenant
`user_learning_patterns` and `transaction_embeddings` are always scoped to `(tenant_id, user_id)`. User A's corrections must never influence User B's categorizations. The pgvector similarity query must always include `WHERE user_id = $current_user`.

### 3. Every DB query must filter by tenant_id (and usually user_id)
Derive `tenant_id` and `user_id` from the validated JWT via `get_tenant_context()` — never from the request body. Return `404` (not `403`) when a resource isn't found under the current tenant context, to prevent enumeration attacks.

### 4. Files are stored by UUID, never by original filename
`statements.file_path` is always `{tenant_id}/{uuid4()}.{ext}`. The original filename lives only in `statements.filename`. `StorageService.save()` enforces this — never bypass it.

### 5. Duplicate transactions are detected at two layers
- **Layer 1**: SHA-256 of the file (`statements.file_hash`) — reject duplicate file uploads with 409
- **Layer 2**: `(user_id, normalized_merchant, amount, date ±1 day)` match in `extract_transactions` task — sets `is_duplicate=TRUE`, skips review queue, copies confirmed category if already reviewed
- Analytics always filter `WHERE is_duplicate = FALSE`

---

## Key Architectural Patterns

### Auth dependency chain (every protected route)
```
HTTPBearer() → Auth0JWKSClient.validate(token) → get_current_user() → get_tenant_context()
```
`get_tenant_context()` returns a `TenantContext(tenant_id, user_id, role)` that every repository method receives as its first argument.

For admin-only endpoints, add `Depends(require_role("owner", "admin"))` to the route.

### Repository pattern (all DB access)
Every entity has a repository in `app/db/repositories/`. No raw SQL or direct model queries in routes or services. Every repository method signature: `async def method(self, db: AsyncSession, ctx: TenantContext, ...) -> Model`.

### Celery task chain (statement processing)
```
parse_statement → extract_transactions → normalize_transactions → categorize_transactions
```
Each task updates `statements.status` and `jobs.progress` before chaining. The `llm` queue handles `categorize_transactions` with a Redis token bucket rate-limiter (10 LLM calls/min per tenant). Learning tasks (`process_feedback`) run in the `learning` queue after user review actions — they are fire-and-forget from the API's perspective.

### 5-Stage Categorization Pipeline (`app/pipelines/categorization_pipeline.py`)

| Stage | Mechanism | Short-circuits at |
|---|---|---|
| 1 | `merchant_aliases` exact/prefix/regex match | confidence ≥ 0.95 |
| 2 | `user_learning_patterns` lookup | confidence ≥ 0.85 AND match_count ≥ 5 |
| 3 | pgvector cosine similarity (top-5 confirmed txns for this user) | similarity ≥ 0.92 |
| 4 | Claude `claude-sonnet-4-6` tool_use (JSON output) | never (always goes to Stage 5) |
| 5 | Human review | — |

Confidence formula: `max(s1*1.0, s2*0.85, s3*0.75, s4*0.65) + 0.05*(agreeing_stages-1)`, capped at 0.98. Full per-stage breakdown stored in `transactions.confidence_breakdown` (JSONB).

### PII handling
`users.email` is **never stored in plaintext**. Use `encryption.py` Fernet encrypt → store in `email_encrypted` (BYTEA). Store SHA-256 hash in `email_hash` for indexed lookup. The `ENCRYPTION_KEY` env var holds the Fernet key.

### Audit logging
Every state-changing API call writes to `audit_logs` (partitioned monthly by `created_at`). The audit middleware in `app/main.py` handles this automatically — do not add manual audit writes in individual routes.

---

## Celery Queues

| Queue | Workers | What runs there |
|---|---|---|
| `default` | 4 concurrent | `parse_statement`, `extract_transactions`, `normalize_transactions` |
| `llm` | 2 concurrent | `categorize_transactions` (rate-limited for Anthropic API) |
| `learning` | 2 concurrent | `process_feedback`, `update_learning_pattern`, `update_embeddings` |
| `analytics` | shared with learning | `generate_analytics_cache` |
| `maintenance` | shared with learning | `refresh_fx_rates`, `create_audit_partition`, `cleanup_stale_jobs` |

---

## Environment Variables (key ones)

```
DATABASE_URL        postgresql+asyncpg://txcat:<pass>@postgres:5432/txcat
REDIS_URL           redis://:<pass>@redis:6379/0
AUTH0_DOMAIN        your-tenant.us.auth0.com
AUTH0_AUDIENCE      https://api.txcat.io
ANTHROPIC_API_KEY   sk-ant-...
ENCRYPTION_KEY      <Fernet key — generate once with Fernet.generate_key()>
STORAGE_BACKEND     local   (or "s3" to switch to S3)
STORAGE_ROOT        /app/uploads
```

See `.env.example` for the full list.

---

## Detailed Specs

`IMPLEMENTATION_PLAN.md` (project root) contains:
- Full DB schema for all 14 tables with column names, types, indexes, and constraints
- Entity relationship diagram (Mermaid)
- Complete data flow diagram from file upload through confirmed transaction
- Deduplication spec (Sections 6)
- File storage design and `StorageService` interface (Section 7)
- Auth0 free-tier capabilities and workarounds (Section 4)
- Guide for making mid-implementation changes without breaking existing data (Section 5)
