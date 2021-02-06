from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.board import Board as engine_Board
from picaro.engine.character import Character as engine_Character, Encounter, EncounterActions, EncounterOutcome, Tableau as engine_Tableau
from picaro.engine.types import Countries, DrawnCard, EncounterCheck, Hex, Terrains, Token, TokenTypes


@dataclass(frozen=True)
class Player:
    id: int
    name: str


@dataclass(frozen=True)
class Board:
    hexes: Sequence[Hex]
    tokens: Sequence[Token]

    @classmethod
    def from_engine_Board(self, board: engine_Board) -> "Board":
        return Board(hexes=tuple(board.hexes.values()), tokens=tuple(board.tokens.values()))


@dataclass(frozen=True)
class CardPreview:
    id: int
    name: str
    checks: Sequence[EncounterCheck]
    age: int
    location_name: str

    @classmethod
    def from_DrawnCard(cls, drawn_card: DrawnCard) -> "CardPreview":
        # in the future might be able to preview more checks
        return CardPreview(id=drawn_card.card.id, name=drawn_card.card.template.name, checks=drawn_card.card.checks[0:1], age=drawn_card.age, location_name=drawn_card.location_name)


@dataclass(frozen=True)
class Tableau:
    cards: Sequence[CardPreview]
    encounter: Optional[Encounter]
    remaining_turns: int
    luck: int

    @classmethod
    def from_engine_Tableau(cls, tableau: engine_Tableau) -> "Tableau":
        return Tableau(cards=[CardPreview.from_DrawnCard(card) for card in tableau.cards], encounter=tableau.encounter, remaining_turns=tableau.remaining_turns, luck=tableau.luck)


@dataclass(frozen=True)
class Character:
    name: str
    player_id: str
    skills: Dict[str, int]
    job: str
    health: int
    coins: int
    resources: int
    reputation: int
    quest: int
    location: str
    hex: str
    tableau: Optional[Tableau]

    @classmethod
    def from_engine_Character(cls, character: engine_Character, locs: Tuple[str, str]) -> "Character":
        return Character(
            name=character.name,
            player_id=character.player_id,
            skills=character.skills,
            job=character.job_name,
            health=character.health,
            coins=character.coins,
            resources=character.resources,
            reputation=character.reputation,
            quest=character.quest,
            location=locs[0],
            hex=locs[1],
            tableau=Tableau.from_engine_Tableau(character.tableau),
        )


@dataclass(frozen=True)
class StartEncounterRequest:
    card_id: int


@dataclass(frozen=True)
class StartEncounterResponse:
    pass


@dataclass(frozen=True)
class ResolveEncounterRequest:
    actions: EncounterActions


@dataclass(frozen=True)
class ResolveEncounterResponse:
    outcome: Optional[EncounterOutcome]


@dataclass(frozen=True)
class CampRequest:
    rest: bool


@dataclass(frozen=True)
class CampResponse:
    pass


@dataclass(frozen=True)
class TravelRequest:
    route: Sequence[str]


@dataclass(frozen=True)
class TravelResponse:
    pass


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
