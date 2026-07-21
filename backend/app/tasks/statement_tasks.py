import asyncio
import uuid

import structlog

from app.agents.statement_agent import StatementAgent
from app.db.base import WorkerSessionLocal
from app.db.models.job import JobStatus
from app.db.models.statement import FileType, StatementStatus
from app.db.models.transaction import Transaction
from app.db.repositories.job_repo import JobRepository
from app.db.repositories.statement_repo import StatementRepository
from app.db.repositories.transaction_repo import TransactionRepository
from app.services.storage_service import get_storage_service
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_statement_repo = StatementRepository()
_job_repo = JobRepository()
_transaction_repo = TransactionRepository()
_statement_agent = StatementAgent()
_storage = get_storage_service()


async def _parse_statement(statement_id: uuid.UUID) -> None:
    async with WorkerSessionLocal() as db:
        statement = await _statement_repo.get_by_id_for_worker(db, statement_id)
        if statement is None:
            logger.warning("parse_statement.statement_not_found", statement_id=str(statement_id))
            return

        logger.info("parse_statement.received", statement_id=str(statement_id))
        await _statement_repo.update_status(db, statement, StatementStatus.parsed)
        await db.commit()

    extract_transactions.delay(str(statement_id))


@celery_app.task(name="app.tasks.statement_tasks.parse_statement")
def parse_statement(statement_id: str) -> None:
    asyncio.run(_parse_statement(uuid.UUID(statement_id)))


async def _extract_transactions(statement_id: uuid.UUID) -> None:
    async with WorkerSessionLocal() as db:
        statement = await _statement_repo.get_by_id_for_worker(db, statement_id)
        if statement is None:
            logger.warning("extract_transactions.statement_not_found", statement_id=str(statement_id))
            return

        job = (
            await _job_repo.get_by_id_for_worker(db, statement.job_id)
            if statement.job_id is not None
            else None
        )

        if statement.file_type != FileType.xlsx:
            error = f"extract_transactions does not yet support {statement.file_type.value} files"
            logger.warning(
                "extract_transactions.unsupported_file_type",
                statement_id=str(statement_id),
                file_type=statement.file_type.value,
            )
            await _statement_repo.update_status(
                db, statement, StatementStatus.failed, error_message=error
            )
            if job is not None:
                await _job_repo.update_progress(
                    db, job, progress=job.progress, status=JobStatus.failed, error_message=error
                )
            await db.commit()
            return

        content = _storage.read(statement.file_path)
        raw_rows = _statement_agent.parse_xlsx(content)

        transactions = [
            Transaction(
                tenant_id=statement.tenant_id,
                user_id=statement.user_id,
                statement_id=statement.id,
                account_id=statement.account_id,
                raw_description=row.raw_description,
                transaction_date=row.transaction_date,
                raw_amount=row.raw_amount,
            )
            for row in raw_rows
        ]
        await _transaction_repo.bulk_create(db, transactions)

        await _statement_repo.update_status(
            db, statement, StatementStatus.normalizing, transaction_count=len(transactions)
        )
        if job is not None:
            await _job_repo.update_progress(db, job, progress=25, status=JobStatus.running)
        await db.commit()

        logger.info(
            "extract_transactions.completed",
            statement_id=str(statement_id),
            transaction_count=len(transactions),
        )


@celery_app.task(name="app.tasks.statement_tasks.extract_transactions")
def extract_transactions(statement_id: str) -> None:
    asyncio.run(_extract_transactions(uuid.UUID(statement_id)))
