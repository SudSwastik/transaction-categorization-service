import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.db.models.job import Job, JobStatus, JobType


class JobRepository:
    async def create(
        self,
        db: AsyncSession,
        ctx: TenantContext,
        *,
        job_type: JobType,
        entity_id: uuid.UUID | None = None,
    ) -> Job:
        job = Job(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            job_type=job_type,
            entity_id=entity_id,
        )
        db.add(job)
        await db.flush()
        return job

    async def get_by_id(self, db: AsyncSession, ctx: TenantContext, job_id: uuid.UUID) -> Job | None:
        job = await db.get(Job, job_id)
        if job is None or job.tenant_id != ctx.tenant_id or job.user_id != ctx.user_id:
            return None
        return job

    async def get_by_id_for_worker(self, db: AsyncSession, job_id: uuid.UUID) -> Job | None:
        """Unscoped lookup for background tasks — see StatementRepository.get_by_id_for_worker."""
        return await db.get(Job, job_id)

    async def update_progress(
        self,
        db: AsyncSession,
        job: Job,
        *,
        progress: int,
        status: JobStatus | None = None,
        error_message: str | None = None,
    ) -> Job:
        job.progress = progress
        if status is not None:
            job.status = status
        if error_message is not None:
            job.error_message = error_message
        await db.flush()
        return job
