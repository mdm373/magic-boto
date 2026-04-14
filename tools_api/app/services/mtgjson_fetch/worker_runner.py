"""Celery worker orchestration for async MTGJSON fetch jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EditionModel, MtgjsonFetchEditionState, MtgjsonFetchJobEditionModel
from app.repository.edition_repo import EditionRepo
from app.repository.mtgjson_fetch_job_repo import MtgjsonFetchJobRepo
from app.services.mtgjson_fetch.fetch_job import create_mtgjson_fetch_job
from app.services.mtgjson_fetch.model_mapper import MtgJsonModelMapper
from settings import Settings

_SET_LIST_REL = "api/v5/SetList.json.gz"
_ERR_MSG_MAX = 8000


async def run_mtgjson_fetch_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    settings: Settings,
) -> None:
    """Run one fetch job: refresh SetList, ingest pending sets, finalize orphan rows."""
    repo = MtgjsonFetchJobRepo()
    edition_catalog = EditionRepo()
    mapper = MtgJsonModelMapper()

    job = await repo.get_job(session, job_id)
    if job is None:
        raise ValueError(f"MTGJSON fetch job {job_id} not found.")
    if job.ended_at is not None:
        logger.info("MTGJSON fetch job {} already finished; skipping.", job_id)
        return

    await repo.mark_job_started(session, job_id)
    await session.commit()

    ingest = create_mtgjson_fetch_job(
        session=session,
        settings=settings,
        always_refresh_set_codes=frozenset(),
    )
    file_client = ingest.file_client

    main_error: str | None = None
    try:
        file_client.delete_cached_json(_SET_LIST_REL)
        set_list_path, _ = file_client.ensure_cached_json(_SET_LIST_REL)
        all_editions = sorted(mapper.map_editions(set_list_path), key=lambda r: r.set_code)

        existing_codes = await edition_catalog.select_existing_set_codes(session)
        edition_rows = await repo.list_editions_by_job(session, job_id)
        by_code: dict[str, MtgjsonFetchJobEditionModel] = {r.set_code: r for r in edition_rows}

        work: list[EditionModel] = []
        for edition in all_editions:
            in_db = edition.set_code in existing_codes
            row = by_code.get(edition.set_code)
            if not in_db:
                work.append(edition)
            elif row is not None and row.state in (
                MtgjsonFetchEditionState.REQUESTED.value,
                MtgjsonFetchEditionState.INPROGRESS.value,
            ):
                work.append(edition)

        for edition in work:
            if edition.set_code not in by_code:
                row = MtgjsonFetchJobEditionModel(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    set_code=edition.set_code,
                    state=MtgjsonFetchEditionState.REQUESTED.value,
                    updated_cards_count=0,
                )
                session.add(row)
                await session.flush()
                by_code[edition.set_code] = row

            ed_row = by_code[edition.set_code]
            if ed_row.state == MtgjsonFetchEditionState.DONE.value:
                continue

            ed_row.state = MtgjsonFetchEditionState.INPROGRESS.value
            ed_row.started_at = datetime.now(UTC)
            await session.commit()

            rel = f"api/v5/{edition.set_code}.json.gz"
            file_client.delete_cached_json(rel)
            set_path, _ = file_client.ensure_cached_json(rel)

            count = await ingest.ingest_edition_from_json_path(edition, set_path)

            ed_row.state = MtgjsonFetchEditionState.DONE.value
            ed_row.ended_at = datetime.now(UTC)
            ed_row.updated_cards_count = count
            await session.commit()
            existing_codes.add(edition.set_code)

    except Exception as exc:
        main_error = str(exc)[:_ERR_MSG_MAX]
        logger.exception("MTGJSON fetch job {} failed", job_id)

    now = datetime.now(UTC)
    all_rows = await repo.list_editions_by_job(session, job_id)
    orphan_codes: list[str] = []
    for row in all_rows:
        if row.state != MtgjsonFetchEditionState.REQUESTED.value:
            continue
        row.state = MtgjsonFetchEditionState.DONE.value
        row.ended_at = now
        row.updated_cards_count = 0
        orphan_codes.append(row.set_code)

    parts: list[str] = []
    if main_error:
        parts.append(main_error)
    if orphan_codes:
        parts.append(
            "Unknown or unavailable set codes (not in MTGJSON SetList): "
            + ", ".join(sorted(set(orphan_codes)))
        )
    final_err = "\n".join(parts) if parts else None

    await repo.mark_job_finished(session, job_id, error_message=final_err)
    await session.commit()


__all__ = ["run_mtgjson_fetch_job"]
