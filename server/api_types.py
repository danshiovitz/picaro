from typing import Dict, List, NamedTuple, Optional, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.board import Board as engine_Board
from picaro.engine.character import Character as engine_Character, Encounter, EncounterActions, EncounterOutcome, Tableau as engine_Tableau
from picaro.engine.types import Countries, EncounterCheck, DrawnCard, Hex, Terrains, Token, TokenTypes


class Player(NamedTuple):
    id: int
    name: str


class Board(NamedTuple):
    hexes: List[Hex]
    tokens: List[Token]

    @classmethod
    def from_engine_Board(self, board: engine_Board) -> "Board":
        return Board(hexes=list(board.hexes.values()), tokens=list(board.tokens.values()))


class CardPreview(NamedTuple):
    id: int
    name: str
    checks: List[EncounterCheck]
    age: int
    location: str

    @classmethod
    def from_DrawnCard(cls, drawn_card: DrawnCard) -> "CardPreview":
        # in the future might be able to preview more checks
        return CardPreview(id=drawn_card.card.id, name=drawn_card.card.template.name, checks=drawn_card.card.checks[0:1], age=drawn_card.age, location=drawn_card.location.name)


class Tableau(NamedTuple):
    cards: List[CardPreview]
    encounter: Optional[Encounter]
    remaining_turns: int
    luck: int

    @classmethod
    def from_engine_Tableau(cls, tableau: engine_Tableau) -> "Tableau":
        return Tableau(cards=[CardPreview.from_DrawnCard(card) for card in tableau.cards], encounter=tableau.encounter, remaining_turns=tableau.remaining_turns, luck=tableau.luck)


class Character(NamedTuple):
    name: str
    player_id: str
    skills: Dict[str, int]
    job: str
    health: int
    coins: int
    reputation: int
    location: str
    hex: str
    tableau: Optional[Tableau]

    @classmethod
    def from_engine_Character(cls, character: engine_Character, locs: Tuple[str, str]) -> "Character":
        return Character(
            name=character.name,
            player_id=character.player_id,
            skills=character.skills,
            job=character.job.name,
            health=character.health,
            coins=character.coins,
            reputation=character.reputation,
            location=locs[0],
            hex=locs[1],
            tableau=Tableau.from_engine_Tableau(character.tableau),
        )


class StartEncounterRequest(NamedTuple):
    card_id: int


class StartEncounterResponse(NamedTuple):
    error: Optional[str]


class ResolveEncounterRequest(NamedTuple):
    actions: EncounterActions


class ResolveEncounterResponse(NamedTuple):
    error: Optional[str]
    outcome: Optional[EncounterOutcome]


class CampRequest(NamedTuple):
    rest: bool


class CampResponse(NamedTuple):
    error: Optional[str]


class TravelRequest(NamedTuple):
    route: List[str]


class TravelResponse(NamedTuple):
    error: Optional[str]
