"""Edition mapper: convert ORM edition model to API response schema."""

from app.errors import InternalError
from app.models import MtgjsonEditionModel
from app.schema import MtgjsonEdition


class EditionMapper:
    """Map ORM edition model to API response schema."""

    def to_response(self, edition: MtgjsonEditionModel) -> MtgjsonEdition:
        name = (edition.name or "").strip()
        if not name:
            raise InternalError(f"edition set_code={edition.code!r} has no name")
        return MtgjsonEdition(
            set_code=edition.code,
            name=name,
        )
