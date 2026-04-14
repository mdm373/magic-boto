"""ORM: ``magic_boto.mtgjson_fetch_job_editions``."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MtgjsonFetchJobEditionModel(Base):
    """Progress for one set code within a fetch job."""

    __tablename__ = "mtgjson_fetch_job_editions"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.mtgjson_fetch_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    set_code: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_cards_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
