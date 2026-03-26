"""Edition mapper: convert ORM edition model to API response schema."""

from app.models import MagicBotoEditionModel
from app.schema import MtgjsonEdition


class EditionMapper:
    """Map ORM edition model to API response schema."""

    def to_response(self, edition: MagicBotoEditionModel) -> MtgjsonEdition:
        name = (edition.name or "").strip()
        return MtgjsonEdition(
            set_code=edition.set_code,
            name=name,
        )
