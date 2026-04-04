"""Edition mapper: convert ORM edition model to API response schema."""

from app.api_schema import Edition
from app.models.edition_model import EditionModel


class EditionMapper:
    """Map ORM edition model to API response schema."""

    def to_response(self, edition: EditionModel) -> Edition:
        name = (edition.name or "").strip()
        return Edition(
            set_code=edition.set_code,
            name=name,
        )
