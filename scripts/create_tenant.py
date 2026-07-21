#!/usr/bin/env python
"""Provision a new tenant plus its first (owner) user.

Run from the backend's uv environment, e.g.:

    cd backend && uv run python ../scripts/create_tenant.py \\
        --name "Acme Corp" --auth0-id "auth0|abc123"

--auth0-id must be the Auth0 `sub` claim of an account that already exists in
Auth0 (sign them up first) — we link to it, we don't create Auth0 accounts here.
"""
import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models.user import UserRole  # noqa: E402
from app.db.repositories.tenant_repo import TenantRepository  # noqa: E402
from app.db.repositories.user_repo import UserRepository  # noqa: E402


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


async def create_tenant(name: str, auth0_id: str, slug: str | None, role: UserRole) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    tenant_repo = TenantRepository()
    user_repo = UserRepository()
    resolved_slug = slug or _slugify(name)

    async with session_factory() as db:
        if await tenant_repo.get_by_slug(db, resolved_slug) is not None:
            print(f"Tenant slug '{resolved_slug}' is already taken", file=sys.stderr)
            sys.exit(1)

        if await user_repo.get_by_auth0_id(db, auth0_id) is not None:
            print(f"A user with auth0_id '{auth0_id}' already exists", file=sys.stderr)
            sys.exit(1)

        tenant = await tenant_repo.create(db, name=name, slug=resolved_slug)
        user = await user_repo.create(db, tenant_id=tenant.id, auth0_user_id=auth0_id, role=role)
        await db.commit()

        print(f"tenant_id={tenant.id}")
        print(f"user_id={user.id}")
        print(f"slug={tenant.slug}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a tenant and its first owner user.")
    parser.add_argument("--name", required=True, help="Tenant display name, e.g. 'Acme Corp'")
    parser.add_argument(
        "--auth0-id", required=True, help="Owner's Auth0 subject claim, e.g. 'auth0|abc123'"
    )
    parser.add_argument("--slug", default=None, help="URL-safe slug (derived from --name if omitted)")
    parser.add_argument(
        "--role",
        default=UserRole.owner.value,
        choices=[role.value for role in UserRole],
        help="Role for the seeded user (default: owner)",
    )
    args = parser.parse_args()

    asyncio.run(create_tenant(args.name, args.auth0_id, args.slug, UserRole(args.role)))


if __name__ == "__main__":
    main()
