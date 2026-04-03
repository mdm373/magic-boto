"""Shared batch-poll loop for sweep and audit pipelines."""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from collections.abc import Sequence
from typing import Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session_factory
from app.log import configure_cli_logging
from app.models.batch import BatchModel
from app.models.sweep_status import TERMINAL_BATCH_STATUSES
from app.tag.batch.client import BatchApiClient, create_batch_client
from settings import get_settings

from .batch_service import BatchService


class BatchPollProvider(Protocol):
    """Interface a pipeline implements to participate in the shared poll loop."""

    def populate_parser(self, parser: argparse.ArgumentParser) -> None:
        """Configure *parser*: set its description and add pipeline-specific arguments."""
        ...

    async def fetch_batch_ids(
        self, session: AsyncSession, args: argparse.Namespace
    ) -> Sequence[uuid.UUID]:
        """Return all batch IDs for this pipeline run, regardless of status."""
        ...


class BatchPoller:
    """Runs the poll loop for a pipeline."""

    def __init__(
        self,
        provider: BatchPollProvider,
        batch_client: BatchApiClient,
        batch_service: BatchService,
    ) -> None:
        self._provider = provider
        self._batch_client = batch_client
        self._batch_service = batch_service

    def run(self) -> None:
        """Configure logging, parse CLI args, and run the poll loop."""
        configure_cli_logging()
        interval = get_settings().batch_poll_interval_seconds
        parser = argparse.ArgumentParser()
        self._provider.populate_parser(parser)
        parser.add_argument(
            "--wait",
            action="store_true",
            default=False,
            help=f"Loop every {interval}s until all batches reach a terminal state.",
        )
        asyncio.run(self._loop(parser.parse_args()))

    async def _loop(self, args: argparse.Namespace) -> None:
        interval = get_settings().batch_poll_interval_seconds
        session_factory = get_async_session_factory()

        async with session_factory() as session:
            batch_ids = await self._provider.fetch_batch_ids(session, args)

        if not batch_ids:
            logger.info("No batches found for this run.")
            return

        while True:
            async with session_factory() as session:
                batches = await self._batch_service.get_non_terminal_batches_by_ids(
                    session, batch_ids
                )
                if not batches:
                    logger.info("All batches are in a terminal state.")
                    break
                self._poll_batches(batches)
                await session.commit()

            logger.info("{} batch(es) still in progress.", len(batches))

            if not args.wait:
                logger.info("Re-run with --wait to poll automatically.")
                break

            logger.info("Polling again in {}s...", interval)
            time.sleep(interval)

    def _poll_batches(self, batches: Sequence[BatchModel]) -> None:
        """Update status/completed_at in place for each non-terminal batch. Caller must commit."""
        for batch in batches:
            if batch.status in TERMINAL_BATCH_STATUSES:
                continue
            result = self._batch_client.get_batch_status(batch.anthropic_batch_id)
            batch.status = result.processing_status
            if result.ended_at is not None:
                batch.completed_at = result.ended_at


def create_batch_poller(provider: BatchPollProvider) -> BatchPoller:
    return BatchPoller(
        provider=provider,
        batch_client=create_batch_client(),
        batch_service=BatchService(),
    )
