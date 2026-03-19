"""MTGJSON edition (set) table ORM model — maps ``mtgjson.sets``."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MtgjsonEditionModel(Base):
    """ORM model for mtgjson.sets (edition / expansion); PK ``code`` for card FK."""

    __tablename__ = "sets"
    __table_args__ = {"schema": "mtgjson"}

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
