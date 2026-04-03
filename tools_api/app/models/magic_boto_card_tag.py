"""ORM: ``magic_boto.card_tags`` junction (oracle_id ↔ tag).

Tags are applied to oracle identities, not individual printings.
One tag on an oracle_id covers every printing of that card.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .magic_boto_tag import MagicBotoTagModel


class MagicBotoCardTagModel(Base):
    """Junction table linking oracle card identities to user-defined tags.

    ``oracle_id`` is the Scryfall oracle identifier shared by all printings of
    the same card.  No FK is declared because ``oracle_id`` is not a unique key
    on ``magic_boto.cards``; uniqueness is enforced by the PK on this table.
    """

    __tablename__ = "card_tags"
    __table_args__ = {"schema": "magic_boto"}

    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("magic_boto.tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    oracle_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    tag: Mapped[MagicBotoTagModel] = relationship(
        "MagicBotoTagModel",
        lazy="selectin",
        viewonly=True,
    )
