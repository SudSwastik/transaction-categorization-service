import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.statement import FileType, StatementStatus


class StatementUploadResponse(BaseModel):
    statement_id: uuid.UUID
    job_id: uuid.UUID


class StatementStatusResponse(BaseModel):
    status: StatementStatus
    progress: int


class StatementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: FileType
    status: StatementStatus
    transaction_count: int | None
    created_at: datetime


class StatementListResponse(BaseModel):
    items: list[StatementListItem]
