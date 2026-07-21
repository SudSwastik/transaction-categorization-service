import time
from functools import lru_cache
from typing import Any, cast

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.core.config import get_settings


class TokenValidationError(Exception):
    """Raised when a bearer token fails Auth0 JWKS validation."""


class Auth0JWKSClient:
    """Fetches and caches Auth0's JWKS, validates RS256-signed access tokens."""

    def __init__(self, domain: str, audience: str, cache_ttl_seconds: int) -> None:
        self._audience = audience
        self._issuer = f"https://{domain}/"
        self._jwks_url = f"https://{domain}/.well-known/jwks.json"
        self._cache_ttl_seconds = cache_ttl_seconds
        self._jwks: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    async def _fetch_jwks(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self._jwks_url)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def _get_jwks(self, *, force_refresh: bool = False) -> dict[str, Any]:
        is_stale = time.monotonic() - self._jwks_fetched_at > self._cache_ttl_seconds
        if self._jwks is None or is_stale or force_refresh:
            self._jwks = await self._fetch_jwks()
            self._jwks_fetched_at = time.monotonic()
        return self._jwks

    async def _get_signing_key(self, kid: str) -> dict[str, Any]:
        jwks = await self._get_jwks()
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key is None:
            # Auth0 may have rotated keys since our last fetch — refresh once and retry
            jwks = await self._get_jwks(force_refresh=True)
            key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key is None:
            raise TokenValidationError(f"No matching JWKS key found for kid={kid!r}")
        return cast(dict[str, Any], key)

    async def validate(self, token: str) -> dict[str, Any]:
        """Verify signature, issuer, audience, and expiry. Returns decoded claims."""
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise TokenValidationError("Malformed token header") from exc

        kid = header.get("kid")
        if not kid:
            raise TokenValidationError("Token header missing 'kid'")

        signing_key = await self._get_signing_key(kid)

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
            return claims
        except ExpiredSignatureError as exc:
            raise TokenValidationError("Token has expired") from exc
        except JWTClaimsError as exc:
            raise TokenValidationError(f"Invalid token claims: {exc}") from exc
        except JWTError as exc:
            raise TokenValidationError(f"Invalid token: {exc}") from exc


@lru_cache
def get_auth0_client() -> Auth0JWKSClient:
    settings = get_settings()
    return Auth0JWKSClient(
        domain=settings.AUTH0_DOMAIN,
        audience=settings.AUTH0_AUDIENCE,
        cache_ttl_seconds=settings.AUTH0_JWKS_CACHE_TTL_SECONDS,
    )
