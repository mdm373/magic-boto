"""Fetch orchestration job with constructor-injected dependencies."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EditionModel
from app.repository.card_keyword_repo import CardKeywordRepo
from app.repository.card_meta_repo import CardMetaRepo
from app.repository.card_repo import CardRepo
from app.repository.card_subtype_repo import CardSubtypeRepo
from app.repository.card_supertype_repo import CardSupertypeRepo
from app.repository.card_type_repo import CardTypeRepo
from app.repository.edition_repo import EditionRepo
from settings import Settings

from .file_client import MtgJsonFileClient
from .model_mapper import MtgJsonModelMapper

_SET_LIST_REL = "api/v5/SetList.json.gz"


class MtgJsonFetchJob:
    """Orchestrates MTGJSON fetch + ingest into magic_boto tables."""

    def __init__(
        self,
        session: AsyncSession,
        file_client: MtgJsonFileClient,
        mapper: MtgJsonModelMapper,
        editions: EditionRepo,
        cards: CardRepo,
        card_types: CardTypeRepo,
        card_subtypes: CardSubtypeRepo,
        card_supertypes: CardSupertypeRepo,
        card_keywords: CardKeywordRepo,
        card_meta: CardMetaRepo,
        batch_size: int,
        always_refresh_set_codes: frozenset[str],
    ) -> None:
        self._session = session
        self._file_client = file_client
        self._mapper = mapper
        self._editions = editions
        self._cards = cards
        self._card_types = card_types
        self._card_subtypes = card_subtypes
        self._card_supertypes = card_supertypes
        self._card_keywords = card_keywords
        self._card_meta = card_meta
        self._batch_size = batch_size
        self._always_refresh_set_codes = always_refresh_set_codes

    @property
    def file_client(self) -> MtgJsonFileClient:
        """Expose the file client for orchestrators that delete cache outside ``run``."""
        return self._file_client

    async def ingest_edition_from_json_path(
        self, edition: EditionModel, set_json_path: Path
    ) -> int:
        """Parse one set JSON and upsert edition + related rows; returns inserted card count."""
        payload = self._mapper.map_set_payload(path=set_json_path, set_code=edition.set_code)
        async with self._session.begin():
            await self._editions.insert(self._session, edition)
            await self._cards.insert_many(self._session, payload.cards, batch_size=self._batch_size)
            await self._card_types.insert_many(
                self._session, payload.card_types, batch_size=self._batch_size
            )
            await self._card_subtypes.insert_many(
                self._session, payload.card_subtypes, batch_size=self._batch_size
            )
            await self._card_supertypes.insert_many(
                self._session, payload.card_supertypes, batch_size=self._batch_size
            )
            await self._card_keywords.insert_many(
                self._session, payload.card_keywords, batch_size=self._batch_size
            )
            await self._card_meta.insert_many(
                self._session, payload.card_meta, batch_size=self._batch_size
            )
        return len(payload.cards)

    async def run(self) -> list[str]:
        """Ingest new sets and optionally re-ingest cache-busted sets.

        Returns set codes whose per-set JSON was fetched from the network (not a local cache hit).
        """
        existing_codes = await self._editions.select_existing_set_codes(self._session)
        await self._session.commit()

        refresh = self._always_refresh_set_codes
        if refresh:
            logger.info(
                "MTGJSON cache bust before download for: {}",
                ", ".join(sorted(refresh)),
            )

        self._file_client.delete_cached_json(_SET_LIST_REL)
        set_list_path, _ = self._file_client.ensure_cached_json(_SET_LIST_REL)
        editions = sorted(self._mapper.map_editions(set_list_path), key=lambda r: r.set_code)
        pending = [
            row for row in editions if row.set_code not in existing_codes or row.set_code in refresh
        ]
        reingest = sorted(
            {
                row.set_code
                for row in pending
                if row.set_code in refresh and row.set_code in existing_codes
            }
        )
        if reingest:
            logger.info("Re-importing cards for editions already in DB: {}", ", ".join(reingest))
        total = len(pending)
        sets_downloaded: list[str] = []
        for i, edition in enumerate(pending, start=1):
            rel = f"api/v5/{edition.set_code}.json.gz"
            bust = edition.set_code in refresh
            set_path, did_download = self._file_client.ensure_cached_json(rel, bust_cache=bust)
            if did_download:
                sets_downloaded.append(edition.set_code)
            await self.ingest_edition_from_json_path(edition, set_path)
            logger.info("[{}/{}] {}", i, total, edition.set_code)

        return sets_downloaded


def create_mtgjson_fetch_job(
    *,
    session: AsyncSession,
    settings: Settings,
    always_refresh_set_codes: frozenset[str],
) -> MtgJsonFetchJob:
    """Wire default file client, mapper, and repos for ``MtgJsonFetchJob``."""
    return MtgJsonFetchJob(
        session=session,
        file_client=MtgJsonFileClient(settings),
        mapper=MtgJsonModelMapper(),
        editions=EditionRepo(),
        cards=CardRepo(),
        card_types=CardTypeRepo(),
        card_subtypes=CardSubtypeRepo(),
        card_supertypes=CardSupertypeRepo(),
        card_keywords=CardKeywordRepo(),
        card_meta=CardMetaRepo(),
        batch_size=settings.mtgjson_insert_batch_size,
        always_refresh_set_codes=always_refresh_set_codes,
    )
