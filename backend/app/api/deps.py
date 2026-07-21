import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.context import TenantContext
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import Auth0JWKSClient, TokenValidationError, get_auth0_client
from app.db.models.user import UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


def _get_claim(claims: dict[str, Any], key: str) -> Any:
    """Auth0 requires custom claims to be namespaced with a URL; fall back to a
    bare key so tests/local tooling can issue tokens without the namespace."""
    settings = get_settings()
    namespaced_key = f"{settings.AUTH0_AUDIENCE}/{key}"
    if namespaced_key in claims:
        return claims[namespaced_key]
    if key in claims:
        return claims[key]
    raise UnauthorizedError(f"Token is missing required claim '{key}'")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth0_client: Auth0JWKSClient = Depends(get_auth0_client),
) -> dict[str, Any]:
    """Validate the bearer token against Auth0's JWKS and return its claims."""
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    try:
        return await auth0_client.validate(credentials.credentials)
    except TokenValidationError as exc:
        raise UnauthorizedError(str(exc)) from exc


async def get_tenant_context(
    claims: dict[str, Any] = Depends(get_current_user),
) -> TenantContext:
    """Extract tenant_id/user_id/role injected into the JWT by the Auth0 post-login Action."""
    try:
        tenant_id = uuid.UUID(str(_get_claim(claims, "tenant_id")))
        user_id = uuid.UUID(str(_get_claim(claims, "user_id")))
        role = UserRole(_get_claim(claims, "role"))
    except ValueError as exc:
        raise UnauthorizedError("Token tenant context claims are malformed") from exc

    return TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)


def require_role(*allowed_roles: UserRole) -> Callable[[TenantContext], Awaitable[TenantContext]]:
    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.role not in allowed_roles:
            allowed = ", ".join(role.value for role in allowed_roles)
            raise ForbiddenError(f"Requires role in [{allowed}]")
        return ctx

    return _dependency
