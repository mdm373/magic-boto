"""Database connection; uses settings for POSTGRES_*."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast

import asyncpg
from asyncpg import Pool
from asyncpg.pool import PoolConnectionProxy
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.requests import Request

from settings import get_settings

_pool: Pool | None = None


@dataclass(frozen=True, slots=True)
class AsyncSqlalchemyResources:
    """Engine + session factory for one process or one ``asyncio.run()`` (CLI / Celery)."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[AsyncSession]:
        """One unit of work: commit on success, rollback on error. Callers do not commit.

        Use for CLI, MCP, and other app code. Does not dispose the engine (unlike
        :meth:`worker_session`). For one-shot CLIs, prefer :func:`cli_session_scope`.
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    @asynccontextmanager
    async def worker_session(self) -> AsyncIterator[AsyncSession]:
        """Celery worker unit: :meth:`session_scope` then dispose engine.

        Enqueue follow-up Celery work *after* exiting this context so commits are visible first.
        Prefer :func:`worker_session_scope` at call sites to avoid nesting.
        """
        try:
            async with self.session_scope() as session:
                yield session
        finally:
            await self.engine.dispose()


def build_async_sqlalchemy_resources() -> AsyncSqlalchemyResources:
    """Create a new async engine and session factory (no process-wide singleton)."""
    engine = create_async_engine(
        get_async_sqlalchemy_url(),
        pool_pre_ping=True,
        echo=False,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return AsyncSqlalchemyResources(engine=engine, session_factory=session_factory)


@asynccontextmanager
async def sqlalchemy_resources_lifespan() -> AsyncIterator[AsyncSqlalchemyResources]:
    """CLI / one-shot async entrypoints: build resources, yield, dispose engine."""
    resources = build_async_sqlalchemy_resources()
    try:
        yield resources
    finally:
        await resources.engine.dispose()


@asynccontextmanager
async def cli_session_scope() -> AsyncIterator[AsyncSession]:
    """CLI one-shot: engine + one committing session, then dispose.

    Same as nesting ``sqlalchemy_resources_lifespan`` and ``session_scope``. Prefer
    :func:`sqlalchemy_resources_lifespan` when you need several sessions on one engine.
    """
    async with sqlalchemy_resources_lifespan() as r:
        async with r.session_scope() as session:
            yield session


@asynccontextmanager
async def worker_session_scope() -> AsyncIterator[AsyncSession]:
    """Celery task body: :meth:`AsyncSqlalchemyResources.worker_session` (commit + dispose engine).

    Prefer this over ``build_async_sqlalchemy_resources()`` + ``worker_session()`` nesting.
    """
    resources = build_async_sqlalchemy_resources()
    async with resources.worker_session() as session:
        yield session


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


def get_async_sqlalchemy(request: Request) -> AsyncSqlalchemyResources:  # FastAPI/Starlette
    """FastAPI dependency: SQLAlchemy resources attached in app lifespan."""
    return cast(AsyncSqlalchemyResources, request.app.state.async_sqlalchemy)


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one ``AsyncSession`` per request (from app lifespan resources)."""
    resources = get_async_sqlalchemy(request)
    async with resources.session_factory() as session:
        yield session
