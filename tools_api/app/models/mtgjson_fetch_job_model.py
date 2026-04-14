"""ORM: ``magic_boto.mtgjson_fetch_jobs``."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MtgjsonFetchJobModel(Base):
    """One async MTGJSON catalog fetch run (Celery-backed)."""

    __tablename__ = "mtgjson_fetch_jobs"
    __table_args__ = {"schema": "magic_boto"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
