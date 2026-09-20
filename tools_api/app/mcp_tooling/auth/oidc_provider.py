"""``TokenVerifier`` that validates bearer JWTs against an OIDC provider's JWKS."""

from __future__ import annotations

import asyncio

import jwt
from jwt import PyJWKClient
from loguru import logger
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .settings import OidcAuthSettings


class OidcAuthProvider(TokenVerifier):
    """Verifies RS256 access tokens issued by an OIDC provider (resource-server pattern).

    The OIDC provider (Authelia) remains the authorization server; this MCP server never runs
    an OAuth flow itself — it only checks that a presented bearer token was signed by it, is
    unexpired, and carries the expected audience.
    """

    def __init__(self, settings: OidcAuthSettings) -> None:
        self._settings = settings
        self._jwks_client = PyJWKClient(settings.jwks_url, lifespan=settings.jwks_cache_seconds)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = await asyncio.to_thread(self._jwks_client.get_signing_key_from_jwt, token)
            claims = await asyncio.to_thread(
                jwt.decode,
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer_url,
                options={"require": ["exp", "iat"]},
            )
        except jwt.PyJWTError as exc:
            logger.warning("MCP bearer token rejected: {}", exc)
            return None

        scope_claim = claims.get("scope", "")
        scopes = scope_claim.split() if isinstance(scope_claim, str) else []
        client_id = claims.get("azp") or claims.get("client_id") or claims.get("sub") or ""

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=claims.get("exp"),
            resource=self._settings.resource_server_url,
        )
