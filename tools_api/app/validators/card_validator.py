from app.errors import InvalidRequestError
from app.schema import CardsQuery


class CardQueryValidator:
    """Validation helpers for MTGJSON card endpoints."""

    def validate_card_query(self, query: CardsQuery) -> CardsQuery:
        if query.is_empty():
            raise InvalidRequestError("Provide search criteria")
        return query
