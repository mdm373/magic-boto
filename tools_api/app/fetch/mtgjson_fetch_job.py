"""Fetch orchestration job with constructor-injected dependencies."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.magic_boto_repositories import (
    MagicBotoRepositories,
    create_magic_boto_repositories,
)
from settings import Settings

from .mtgjson_file_client import MtgJsonFileClient
from .mtgjson_model_mapper import MtgJsonModelMapper

_SET_LIST_REL = "api/v5/SetList.json.gz"


class MtgJsonFetchJob:
    """Orchestrates MTGJSON fetch + ingest into magic_boto tables."""

    def __init__(
        self,
        session: AsyncSession,
        file_client: MtgJsonFileClient,
        mapper: MtgJsonModelMapper,
        repository: MagicBotoRepositories,
    ) -> None:
        self._session = session
        self._file_client = file_client
        self._mapper = mapper
        self._repository = repository

    async def run(self) -> None:
        existing_codes = await self._repository.editions.select_existing_set_codes()
        await self._session.commit()

        set_list_path, _ = self._file_client.ensure_cached_json(_SET_LIST_REL)
        editions = sorted(self._mapper.map_editions(set_list_path), key=lambda r: r.set_code)
        pending = [row for row in editions if row.set_code not in existing_codes]
        total = len(pending)
        for i, edition in enumerate(pending, start=1):
            rel = f"api/v5/{edition.set_code}.json.gz"
            set_path, _ = self._file_client.ensure_cached_json(rel, check_freshness=False)
            payload = self._mapper.map_set_payload(path=set_path, set_code=edition.set_code)
            async with self._session.begin():
                await self._repository.editions.insert(edition)
                await self._repository.cards.insert_many(payload.cards)
                await self._repository.card_types.insert_many(payload.card_types)
                await self._repository.card_subtypes.insert_many(payload.card_subtypes)
                await self._repository.card_supertypes.insert_many(payload.card_supertypes)
                await self._repository.card_keywords.insert_many(payload.card_keywords)
                await self._repository.card_meta.insert_many(payload.card_meta)
            logger.info("[{}/{}] {}", i, total, edition.set_code)


def create_mtgjson_fetch_job(*, session: AsyncSession, settings: Settings) -> MtgJsonFetchJob:
    """Wire default file client, mapper, and repository for ``MtgJsonFetchJob``."""
    return MtgJsonFetchJob(
        session=session,
        file_client=MtgJsonFileClient(settings),
        mapper=MtgJsonModelMapper(),
        repository=create_magic_boto_repositories(
            session,
            batch_size=settings.mtgjson_insert_batch_size,
        ),
    )
