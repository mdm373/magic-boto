"""OIDC-backed OAuth resource-server auth for the MCP server (Authelia)."""

from __future__ import annotations

from .oidc_provider import OidcAuthProvider
from .settings import OidcAuthSettings, oidc_auth_settings_from_env

__all__ = [
    "OidcAuthProvider",
    "OidcAuthSettings",
    "oidc_auth_settings_from_env",
]
