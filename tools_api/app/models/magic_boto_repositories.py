"""Bundled ``magic_boto`` table repositories for ingest."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .magic_boto_card_keyword_repository import MagicBotoCardKeywordRepository
from .magic_boto_card_meta_repository import MagicBotoCardMetaRepository
from .magic_boto_card_repository import MagicBotoCardRepository
from .magic_boto_card_subtype_repository import MagicBotoCardSubtypeRepository
from .magic_boto_card_supertype_repository import MagicBotoCardSupertypeRepository
from .magic_boto_card_type_repository import MagicBotoCardTypeRepository
from .magic_boto_edition_repository import MagicBotoEditionRepository


@dataclass(frozen=True, slots=True)
class MagicBotoRepositories:
    """Per-table repos sharing one async session (immutable bundle)."""

    editions: MagicBotoEditionRepository
    cards: MagicBotoCardRepository
    card_types: MagicBotoCardTypeRepository
    card_subtypes: MagicBotoCardSubtypeRepository
    card_supertypes: MagicBotoCardSupertypeRepository
    card_keywords: MagicBotoCardKeywordRepository
    card_meta: MagicBotoCardMetaRepository


def create_magic_boto_repositories(
    session: AsyncSession,
    *,
    batch_size: int,
) -> MagicBotoRepositories:
    """Build default ``magic_boto`` repositories for the given session."""
    return MagicBotoRepositories(
        editions=MagicBotoEditionRepository(session),
        cards=MagicBotoCardRepository(session, batch_size),
        card_types=MagicBotoCardTypeRepository(session, batch_size),
        card_subtypes=MagicBotoCardSubtypeRepository(session, batch_size),
        card_supertypes=MagicBotoCardSupertypeRepository(session, batch_size),
        card_keywords=MagicBotoCardKeywordRepository(session, batch_size),
        card_meta=MagicBotoCardMetaRepository(session, batch_size),
    )
