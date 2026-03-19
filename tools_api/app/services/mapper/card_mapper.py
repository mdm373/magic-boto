"""Card mapper: convert ORM card models to API response schema."""

from app.errors import InternalError
from app.models import CardType, MtgjsonCardModel
from app.schema import MtgjsonCard


def _mana_value_as_int_or_zero(mana_value: float) -> int:
    if not float(mana_value).is_integer():
        return 0
    return int(mana_value)


class CardMapper:
    """Map ORM card model to API response schema."""

    def to_response(self, card: MtgjsonCardModel) -> MtgjsonCard:
        idents = card.identifiers
        if idents is None:
            raise InternalError(f"card uuid={card.uuid!r} has no cardIdentifiers row")
        card_id = (idents.card_id or "").strip()
        oracle_id = (idents.oracle_id or "").strip()
        if not card_id or not oracle_id:
            raise InternalError(f"card uuid={card.uuid!r} missing scryfallId or scryfallOracleId")
        sc = (card.set_code or "").strip()
        if not sc:
            raise InternalError(f"card uuid={card.uuid!r} missing setCode (set FK)")
        card_types_list = [CardType(ct.card_type) for ct in card.card_types]
        return MtgjsonCard(
            name=card.name or "",
            mana_cost=card.mana_cost,
            mana_value=_mana_value_as_int_or_zero(card.mana_value),
            set_code=sc,
            card_id=card_id,
            oracle_id=oracle_id,
            type=card.type,
            card_types=card_types_list,
            rarity=card.rarity,
        )
