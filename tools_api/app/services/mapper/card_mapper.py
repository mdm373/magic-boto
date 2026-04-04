"""Card mapper: convert ORM card models to API response schema."""

from app.api_schema import Card
from app.errors import InternalError
from app.models import CardModel, CardRarity, CardSupertype, CardType
from app.models.color_identity import color_identity_string_to_list


def _map_mana_value(meta_mana: int | None) -> int:
    if meta_mana is None:
        return 0
    return int(meta_mana)


class CardMapper:
    """Map ORM card model to API response schema."""

    def to_response(self, card: CardModel) -> Card:
        scryfall_id = (card.scryfall_id or "").strip()
        if not scryfall_id:
            raise InternalError("catalog printing has no Scryfall id; cannot map to API response")
        oracle_id = (card.oracle_id or "").strip()
        sc = (card.set_code or "").strip()
        card_types_list = [CardType(ct.card_type) for ct in card.card_types]
        card_supertypes_list = [CardSupertype(ct.card_supertype) for ct in card.supertypes]
        card_subtypes_list = [ct.card_subtype for ct in card.subtypes]
        card_keywords_list = [ck.card_keyword for ck in card.keywords]
        mv = _map_mana_value(card.meta.mana_value if card.meta is not None else None)
        try:
            rarity = CardRarity(card.rarity)
        except ValueError as err:
            raise InternalError(f"card scryfall_id={scryfall_id!r} has invalid rarity") from err
        tags = sorted({ct.tag.name for ct in (card.card_tags or [])})
        return Card(
            card_id=card.card_id,
            name=card.name or "",
            mana_cost=card.mana_cost,
            mana_value=mv,
            set_code=sc,
            number=card.collector_number,
            scryfall_id=scryfall_id,
            oracle_id=oracle_id,
            type=card.type_line,
            power=card.power,
            toughness=card.toughness,
            text=card.oracle_text,
            card_types=card_types_list,
            card_supertypes=card_supertypes_list,
            card_subtypes=card_subtypes_list,
            card_keywords=card_keywords_list,
            color_identity=color_identity_string_to_list(card.color_identity),
            rarity=rarity,
            tags=tags,
        )
