from app.errors import InvalidRequestError
from app.schema import EditionsQuery


class EditionQueryValidator:
    """Validation helpers for MTGJSON edition endpoints."""

    def validate_edition_query(self, query: EditionsQuery) -> EditionsQuery:
        if query.is_empty():
            raise InvalidRequestError("Provide search criteria (set_code and/or name)")
        return query
