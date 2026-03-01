"""Database connection; uses settings for POSTGRES_*."""

from collections.abc import AsyncGenerator
from typing import cast

import asyncpg
from asyncpg import Pool
from asyncpg.pool import PoolConnectionProxy
from settings import get_settings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.requests import Request

_pool: Pool | None = None
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    s = get_settings()
    return (
        f"postgresql://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def get_async_sqlalchemy_url() -> str:
    """URL for SQLAlchemy async engine (postgresql+asyncpg)."""
    return get_database_url().replace("postgresql://", "postgresql+asyncpg://", 1)


async def get_pool() -> Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(get_database_url(), min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_conn() -> AsyncGenerator[PoolConnectionProxy, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def inject_conn_into_request(request: Request) -> AsyncGenerator[None, None]:
    """Router-level dependency: set request.state.conn for the request lifetime."""
    async for conn in get_conn():
        request.state.conn = conn
        yield


def get_request_conn(request: Request) -> PoolConnectionProxy:
    """DB connection for this request (routers must use inject_conn_into_request)."""
    return cast(PoolConnectionProxy, request.state.conn)


def get_async_engine() -> AsyncEngine:
    """Create or return the async SQLAlchemy engine (lazy init)."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            get_async_sqlalchemy_url(),
            pool_pre_ping=True,
            echo=False,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create or return the async session factory (lazy init)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def close_async_engine() -> None:
    """Dispose the async engine (call from app lifespan shutdown)."""
    global _async_engine
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None


async def inject_session_into_request(request: Request) -> AsyncGenerator[None, None]:
    """Router-level dependency: set request.state.session for the request lifetime."""
    factory = get_async_session_factory()
    async with factory() as session:
        request.state.session = session
        yield


def get_request_session(request: Request) -> AsyncSession:
    """SQLAlchemy async session for this request (routers must use inject_session_into_request)."""
    return cast(AsyncSession, request.state.session)
