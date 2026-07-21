import uuid
from dataclasses import dataclass

from app.db.models.user import UserRole


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Identity of the caller, derived from a validated JWT — never from request bodies.

    Passed to every repository method (after `db`) so that tenant/user scoping
    happens at the data-access layer, not left to individual routes.
    """

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    role: UserRole
