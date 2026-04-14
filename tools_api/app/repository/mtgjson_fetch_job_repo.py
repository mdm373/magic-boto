"""Repository for ``magic_boto.mtgjson_fetch_jobs`` and ``mtgjson_fetch_job_editions``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MtgjsonFetchEditionState,
    MtgjsonFetchJobEditionModel,
    MtgjsonFetchJobModel,
)


@dataclass(frozen=True, slots=True)
class MtgjsonFetchJobWithEditions:
    """Job row plus ordered edition rows for status APIs."""

    job: MtgjsonFetchJobModel
    editions: tuple[MtgjsonFetchJobEditionModel, ...]


class MtgjsonFetchJobRepo:
    """Pure ORM access for MTGJSON fetch job tables."""

    async def create_job_with_requested_editions(
        self,
        session: AsyncSession,
        *,
        set_codes: frozenset[str],
    ) -> uuid.UUID:
        """Insert a job and one ``requested`` row per set code; caller commits."""
        job = MtgjsonFetchJobModel(id=uuid.uuid4())
        session.add(job)
        await session.flush()
        for code in sorted(set_codes):
            session.add(
                MtgjsonFetchJobEditionModel(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    set_code=code,
                    state=MtgjsonFetchEditionState.REQUESTED.value,
                    updated_cards_count=0,
                )
            )
        await session.flush()
        return job.id

    async def get_job(
        self, session: AsyncSession, job_id: uuid.UUID
    ) -> MtgjsonFetchJobModel | None:
        return await session.get(MtgjsonFetchJobModel, job_id)

    async def load_job_with_editions(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
    ) -> MtgjsonFetchJobWithEditions | None:
        job = await self.get_job(session, job_id)
        if job is None:
            return None
        stmt = (
            select(MtgjsonFetchJobEditionModel)
            .where(MtgjsonFetchJobEditionModel.job_id == job_id)
            .order_by(MtgjsonFetchJobEditionModel.set_code.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return MtgjsonFetchJobWithEditions(job=job, editions=tuple(rows))

    async def list_editions_by_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
    ) -> Sequence[MtgjsonFetchJobEditionModel]:
        stmt = (
            select(MtgjsonFetchJobEditionModel)
            .where(MtgjsonFetchJobEditionModel.job_id == job_id)
            .order_by(MtgjsonFetchJobEditionModel.set_code.asc())
        )
        return (await session.execute(stmt)).scalars().all()

    async def mark_job_started(self, session: AsyncSession, job_id: uuid.UUID) -> None:
        job = await self.require_job(session, job_id)
        if job.started_at is None:
            job.started_at = datetime.now(UTC)

    async def mark_job_finished(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        *,
        error_message: str | None,
    ) -> None:
        job = await self.require_job(session, job_id)
        job.ended_at = datetime.now(UTC)
        job.error_message = error_message

    async def require_job(self, session: AsyncSession, job_id: uuid.UUID) -> MtgjsonFetchJobModel:
        job = await self.get_job(session, job_id)
        if job is None:
            raise ValueError(f"MTGJSON fetch job {job_id} not found.")
        return job


__all__ = ["MtgjsonFetchJobRepo", "MtgjsonFetchJobWithEditions"]
