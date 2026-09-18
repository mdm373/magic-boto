"""Env-driven settings for the MCP resource-server auth gate (Keycloak)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True, slots=True)
class KeycloakAuthSettings:
    """Resolved config for verifying Keycloak-issued bearer tokens."""

    issuer_url: str
    jwks_url: str
    audience: str
    resource_server_url: str
    required_scopes: Sequence[str]
    jwks_cache_seconds: int


def keycloak_auth_settings_from_env() -> KeycloakAuthSettings | None:
    """Build settings from env, or ``None`` when ``TOOLS_MCP_AUTH_ENABLED`` is unset/false.

    Required when enabled: ``KEYCLOAK_ISSUER_URL`` (realm issuer as embedded in tokens'
    ``iss`` claim — the URL clients use to reach Keycloak, e.g.
    ``http://localhost:8180/realms/magic-boto``), ``KEYCLOAK_AUDIENCE`` (expected token
    audience — the MCP client's ID or a dedicated resource indicator), and
    ``TOOLS_MCP_RESOURCE_SERVER_URL`` (this server's externally reachable base URL, used for
    RFC 9728 protected-resource metadata).

    ``KEYCLOAK_JWKS_URL`` is optional and defaults to
    ``{issuer_url}/protocol/openid-connect/certs``. Set it explicitly when this server can't
    reach Keycloak at its public issuer URL — e.g. in
    Docker Compose, browsers/clients reach Keycloak at ``http://localhost:8180`` (so that's the
    ``iss`` this server must validate against), but the ``tools_mcp`` container must fetch keys
    over the compose network at ``http://keycloak:8180/realms/<realm>/protocol/openid-connect/certs``.
    """
    if not _env_flag("TOOLS_MCP_AUTH_ENABLED"):
        return None

    scopes_raw = os.environ.get("TOOLS_MCP_REQUIRED_SCOPES", "").strip()
    required_scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip())

    issuer_url = os.environ["KEYCLOAK_ISSUER_URL"].rstrip("/")
    jwks_url = os.environ.get("KEYCLOAK_JWKS_URL", "").strip().rstrip("/")

    return KeycloakAuthSettings(
        issuer_url=issuer_url,
        jwks_url=jwks_url or f"{issuer_url}/protocol/openid-connect/certs",
        audience=os.environ["KEYCLOAK_AUDIENCE"],
        resource_server_url=os.environ["TOOLS_MCP_RESOURCE_SERVER_URL"].rstrip("/"),
        required_scopes=required_scopes,
        jwks_cache_seconds=int(os.environ.get("KEYCLOAK_JWKS_CACHE_SECONDS", "300")),
    )
