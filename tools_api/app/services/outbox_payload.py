"""Build Anthropic :class:`~app.services.batch_client.Request` lists for sweep outbox rows."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.message_schema import SWEEP_VERDICT_SCHEMA_PATH
from app.models import CardModel
from app.repository import CardRepo
from app.repository.tag_sweep_repo import SweepBatchRecord
from settings import get_settings

from .batch_client import Request
from .card_payload import cards_to_csv
from .sweep_prompt_format import format_sweep_system_prompt


async def build_sweep_outbox_requests(
    session: AsyncSession,
    tag_description: str,
    records: Sequence[SweepBatchRecord],
) -> list[Request]:
    """Build Anthropic batch items from chunk records (same CSV shape as historical submit path)."""
    all_oracle_ids = [oid for r in records for oid in r.oracle_ids]
    card_rows = await CardRepo().fetch_by_oracle_ids(session, all_oracle_ids)
    cards_by_oracle_id: dict[str, CardModel] = {c.oracle_id: c for c in card_rows}
    settings = get_settings()
    system_prompt = format_sweep_system_prompt(tag_description)
    return [
        Request(
            custom_id=record.custom_id,
            messages=[
                cards_to_csv(
                    [
                        cards_by_oracle_id[oid]
                        for oid in record.oracle_ids
                        if oid in cards_by_oracle_id
                    ]
                )
            ],
            model=settings.tag_sweep_model,
            max_tokens=settings.tag_sweep_max_tokens,
            system_prompt=system_prompt,
            output_schema_path=SWEEP_VERDICT_SCHEMA_PATH,
        )
        for record in records
    ]
