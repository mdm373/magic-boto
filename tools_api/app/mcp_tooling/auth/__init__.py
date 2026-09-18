"""Keycloak-backed OAuth resource-server auth for the MCP server."""

from __future__ import annotations

from .keycloak_provider import KeycloakAuthProvider
from .settings import KeycloakAuthSettings, keycloak_auth_settings_from_env

__all__ = [
    "KeycloakAuthProvider",
    "KeycloakAuthSettings",
    "keycloak_auth_settings_from_env",
]
