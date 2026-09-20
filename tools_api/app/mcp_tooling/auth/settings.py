"""Env-driven settings for the MCP resource-server auth gate (OIDC — Authelia)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True, slots=True)
class OidcAuthSettings:
    """Resolved config for verifying OIDC-issued bearer tokens."""

    issuer_url: str
    jwks_url: str
    audience: str
    resource_server_url: str
    required_scopes: Sequence[str]
    jwks_cache_seconds: int


def oidc_auth_settings_from_env() -> OidcAuthSettings | None:
    """Build settings from env, or ``None`` when ``TOOLS_MCP_AUTH_ENABLED`` is unset/false.

    Required when enabled: ``OIDC_ISSUER_URL`` (the provider's issuer as embedded in tokens'
    ``iss`` claim — the URL clients use to reach it, e.g. ``https://magic-boto-authelia.fly.dev``
    in prod or ``http://localhost:9091`` locally), ``OIDC_AUDIENCE`` (expected token audience —
    the MCP client's ID or a dedicated resource indicator), and ``TOOLS_MCP_RESOURCE_SERVER_URL``
    (this server's externally reachable base URL, used for RFC 9728 protected-resource metadata).

    ``OIDC_JWKS_URL`` is optional and defaults to ``{issuer_url}/jwks.json`` (Authelia's JWKS
    path). Set it explicitly when this server can't reach the provider at its public issuer URL —
    e.g. in Docker Compose, browsers/clients reach Authelia at ``http://localhost:9091`` (so
    that's the ``iss`` this server must validate against), but the ``tools_mcp`` container must
    fetch keys over the compose network at ``http://authelia:9091/jwks.json``.
    """
    if not _env_flag("TOOLS_MCP_AUTH_ENABLED"):
        return None

    scopes_raw = os.environ.get("TOOLS_MCP_REQUIRED_SCOPES", "").strip()
    required_scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip())

    issuer_url = os.environ["OIDC_ISSUER_URL"].rstrip("/")
    jwks_url = os.environ.get("OIDC_JWKS_URL", "").strip().rstrip("/")

    return OidcAuthSettings(
        issuer_url=issuer_url,
        jwks_url=jwks_url or f"{issuer_url}/jwks.json",
        audience=os.environ["OIDC_AUDIENCE"],
        resource_server_url=os.environ["TOOLS_MCP_RESOURCE_SERVER_URL"].rstrip("/"),
        required_scopes=required_scopes,
        jwks_cache_seconds=int(os.environ.get("OIDC_JWKS_CACHE_SECONDS", "300")),
    )
