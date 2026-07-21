import uuid

from pydantic import BaseModel

from app.db.models.user import UserRole


class CurrentUserResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str | None = None
    role: UserRole
