import asyncio
import uuid

import structlog

from app.db.base import WorkerSessionLocal
from app.db.models.statement import StatementStatus
from app.db.repositories.statement_repo import StatementRepository
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_statement_repo = StatementRepository()


async def _parse_statement(statement_id: uuid.UUID) -> None:
    async with WorkerSessionLocal() as db:
        statement = await _statement_repo.get_by_id_for_worker(db, statement_id)
        if statement is None:
            logger.warning("parse_statement.statement_not_found", statement_id=str(statement_id))
            return

        logger.info("parse_statement.received", statement_id=str(statement_id))
        await _statement_repo.update_status(db, statement, StatementStatus.parsed)
        await db.commit()


@celery_app.task(name="app.tasks.statement_tasks.parse_statement")
def parse_statement(statement_id: str) -> None:
    asyncio.run(_parse_statement(uuid.UUID(statement_id)))
