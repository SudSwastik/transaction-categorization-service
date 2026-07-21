import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant import Tenant


class TenantRepository:
    """Tenants are created before any TenantContext exists (onboarding), so unlike
    other repositories, these methods are not scoped by TenantContext."""

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        slug: str,
        plan: str = "free",
        base_currency: str = "INR",
    ) -> Tenant:
        tenant = Tenant(name=name, slug=slug, plan=plan, base_currency=base_currency)
        db.add(tenant)
        await db.flush()
        return tenant

    async def get_by_id(self, db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
        return await db.get(Tenant, tenant_id)

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Tenant | None:
        result = await db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def update(self, db: AsyncSession, tenant: Tenant, **fields: Any) -> Tenant:
        for key, value in fields.items():
            setattr(tenant, key, value)
        await db.flush()
        return tenant
