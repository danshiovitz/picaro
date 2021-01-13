from typing import List, NamedTuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.common.engine.types import Countries, FullCard, Hex, Hexmap, Tableau, Terrains, Token, TokenTypes


class CardPreview(NamedTuple):
    name: str
    check: EncounterCheck
    age: int
    location: OffsetCoordinate

    @classmethod
    def from_FullCard(cls, full_card: FullCard) -> "CardPreview":
        return CardPreview(full_card.name, full_card.checks[0], full_card.age, full_card.location)


class ExternalTableau(NamedTuple):
    cards: List[CardPreview]
    remaining_turns: int
    luck: int

    @classmethod
    def from_Tableau(cls, tableau: Tableau) -> "ExternalTableau":
        return tableau([CardPreview.from_FullCard(card) for card in tableau.cards], tableau.remaining_turns, tableau.luck)
