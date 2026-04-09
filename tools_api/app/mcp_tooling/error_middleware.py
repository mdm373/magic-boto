"""MCP error-mapping middleware helpers for tool handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeAlias, TypeVar

from loguru import logger
from mcp import McpError
from mcp.server.fastmcp import FastMCP
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS, ErrorData, Icon, ToolAnnotations
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSqlalchemyResources
from app.errors import InternalError, InvalidRequestError, NotFoundError

P = ParamSpec("P")
R = TypeVar("R")

# Async MCP tool body: ``async def tool(...) -> T``
AsyncToolHandler: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
# Result of ``@app_mcp.tool(...)`` / ``@mcp.tool(...)``: wraps a handler for registration.
RegisterMcpTool: TypeAlias = Callable[[AsyncToolHandler], Any]

# MCP JSON-RPC server error range (-32000..-32099); not all codes are exported on ``mcp.types`` yet.
MCP_NOT_FOUND = -32001


class AppMcp:
    """Binds a :class:`FastMCP` server with app-level tool registration (error mapping)."""

    __slots__ = ("_mcp", "sqlalchemy")

    def __init__(self, mcp: FastMCP[Any]) -> None:
        self._mcp = mcp
        self.sqlalchemy: AsyncSqlalchemyResources | None = None

    @property
    def mcp(self) -> FastMCP[Any]:
        """Underlying FastMCP instance (custom routes, run, etc.)."""
        return self._mcp

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """One MCP tool: session; commit on success, rollback on error; callers do not commit."""
        if self.sqlalchemy is None:
            raise RuntimeError("MCP SQLAlchemy resources not initialized (lifespan not run).")
        async with self.sqlalchemy.session_scope() as session:
            yield session

    def tool(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Icon] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> RegisterMcpTool:
        """Register a tool with :func:`map_app_errors` (same kwargs as :meth:`FastMCP.tool`)."""
        return app_mcp_tool(
            self._mcp,
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=meta,
            structured_output=structured_output,
        )


def app_mcp_tool(
    mcp: FastMCP[Any],
    *,
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    annotations: ToolAnnotations | None = None,
    icons: list[Icon] | None = None,
    meta: dict[str, Any] | None = None,
    structured_output: bool | None = None,
) -> RegisterMcpTool:
    """Combine :meth:`FastMCP.tool` registration with :func:`map_app_errors`."""

    tool_decorator = mcp.tool(
        name=name,
        title=title,
        description=description,
        annotations=annotations,
        icons=icons,
        meta=meta,
        structured_output=structured_output,
    )

    def decorator(func: Callable[P, Awaitable[R]]) -> Any:
        return tool_decorator(map_app_errors(func))

    return decorator


def map_app_errors(
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Map app exceptions to explicit MCP/JSON-RPC errors."""

    @wraps(func)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except InvalidRequestError as exc:
            logger.warning("MCP invalid params: {}", exc)
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message=f"Invalid params: {exc!s}")
            ) from exc
        except NotFoundError as exc:
            logger.warning("MCP not found: {}", exc)
            raise McpError(ErrorData(code=MCP_NOT_FOUND, message=f"Not found: {exc!s}")) from exc
        except InternalError as exc:
            logger.exception("MCP internal error")
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Internal error")) from exc
        except Exception as exc:
            logger.exception("MCP unhandled exception in tool handler")
            raise McpError(
                ErrorData(code=INTERNAL_ERROR, message=f"Unexpected error: {type(exc).__name__}")
            ) from exc

    return wrapped
