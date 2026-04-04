"""Tag service: multi-repo orchestration for tag ↔ card operations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidRequestError
from app.models import CardModel
from app.repository import CardRepo, CardTagEntry, CardTagRepo, TagRepo

_tag_repo = TagRepo()
_card_tag_repo = CardTagRepo()
_card_repo = CardRepo()


class TagService:
    """Multi-repo orchestration for tag ↔ card operations."""

    async def add_card_tags(
        self,
        session: AsyncSession,
        tag_name: str,
        entries: Sequence[CardTagEntry],
    ) -> bool:
        """Apply a tag to the given oracle_ids. Returns False if tag does not exist."""
        tag = await _tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            return False
        oracle_ids = [e.oracle_id for e in entries]
        found = await _card_repo.filter_known_oracle_ids(session, oracle_ids)
        not_found = [oid for oid in oracle_ids if oid not in found]
        if not_found:
            raise InvalidRequestError(f"Oracle IDs not found: {', '.join(not_found)}")
        await _card_tag_repo.upsert(session, tag.id, list(found))
        return True

    async def sample_cards_for_tag(
        self,
        session: AsyncSession,
        tag_name: str,
        limit: int,
    ) -> Sequence[CardModel]:
        """Return up to ``limit`` randomly sampled cards for the given tag."""
        tag = await _tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            return []
        oracle_ids = await _card_tag_repo.sample_oracle_ids(session, tag.id, limit)
        if not oracle_ids:
            return []
        return await _card_repo.fetch_by_oracle_ids(session, oracle_ids)

    async def remove_card_tags(
        self,
        session: AsyncSession,
        tag_name: str,
        oracle_ids: Sequence[str],
    ) -> bool:
        """Remove a tag from the given oracle_ids. Returns False if tag does not exist."""
        tag = await _tag_repo.get_tag_model(session, tag_name)
        if tag is None:
            return False
        found = await _card_repo.filter_known_oracle_ids(session, oracle_ids)
        not_found = [oid for oid in oracle_ids if oid not in found]
        if not_found:
            raise InvalidRequestError(f"Oracle IDs not found: {', '.join(not_found)}")
        await _card_tag_repo.delete(session, tag.id, list(found))
        return True


def create_tag_service() -> TagService:
    return TagService()
