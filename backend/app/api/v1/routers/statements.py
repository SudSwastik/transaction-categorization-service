import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context
from app.core.context import TenantContext
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.db.base import get_db
from app.db.models.job import JobType
from app.db.models.statement import FileType
from app.db.repositories.job_repo import JobRepository
from app.db.repositories.statement_repo import StatementRepository
from app.schemas.statement import (
    StatementListItem,
    StatementListResponse,
    StatementStatusResponse,
    StatementUploadResponse,
)
from app.services.storage_service import (
    FileTooLargeError,
    StorageService,
    UnsupportedFileTypeError,
    get_storage_service,
)
from app.tasks.statement_tasks import parse_statement

router = APIRouter(prefix="/statements", tags=["statements"])

_statement_repo = StatementRepository()
_job_repo = JobRepository()

_READ_CHUNK_SIZE = 1024 * 1024


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Read in chunks and abort as soon as the limit is crossed, so an oversized
    or unbounded upload can't be fully buffered into memory before we reject it."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(f"File exceeds the {max_bytes} byte upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=StatementUploadResponse, status_code=201)
async def upload_statement(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> StatementUploadResponse:
    content = await _read_upload_bounded(file, storage.max_upload_size_bytes)

    try:
        saved = storage.save(tenant_id=ctx.tenant_id, filename=file.filename or "upload", content=content)
    except FileTooLargeError as exc:
        raise PayloadTooLargeError(str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise UnsupportedMediaTypeError(str(exc)) from exc

    file_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

    existing = await _statement_repo.get_by_file_hash(db, ctx, file_hash)
    if existing is not None:
        storage.delete(saved.key)  # don't leave an orphaned duplicate object in the bucket
        raise ConflictError(f"This file was already uploaded (statement_id={existing.id})")

    statement = await _statement_repo.create(
        db,
        ctx,
        filename=saved.original_filename,
        file_path=saved.key,
        file_type=FileType(saved.extension),
        file_size_bytes=saved.size_bytes,
        file_hash=file_hash,
    )
    job = await _job_repo.create(db, ctx, job_type=JobType.parse_statement, entity_id=statement.id)
    await _statement_repo.update_status(db, statement, statement.status, job_id=job.id)
    await db.commit()

    parse_statement.delay(str(statement.id))

    return StatementUploadResponse(statement_id=statement.id, job_id=job.id)


@router.get("/{statement_id}/status", response_model=StatementStatusResponse)
async def get_statement_status(
    statement_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> StatementStatusResponse:
    statement = await _statement_repo.get_by_id(db, ctx, statement_id)
    if statement is None:
        raise NotFoundError("Statement not found")

    progress = 0
    if statement.job_id is not None:
        job = await _job_repo.get_by_id(db, ctx, statement.job_id)
        if job is not None:
            progress = job.progress

    return StatementStatusResponse(status=statement.status, progress=progress)


@router.get("", response_model=StatementListResponse)
async def list_statements(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> StatementListResponse:
    statements = await _statement_repo.list_for_user(db, ctx, limit=limit, offset=offset)
    return StatementListResponse(items=[StatementListItem.model_validate(s) for s in statements])
