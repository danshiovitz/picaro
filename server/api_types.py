from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.engine.character import Character as engine_Character, Encounter as engine_Encounter, EncounterActions, EncounterOutcome, EncounterSingleOutcome
from picaro.engine.types import Board, ChoiceType, Countries, DrawnCard, Effect, EffectType, EncounterCheck, Hex, Terrains, Token, TokenTypes


@dataclass(frozen=True)
class Player:
    id: int
    name: str


@dataclass(frozen=True)
class CardPreview:
    id: str
    name: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
    age: int
    location_name: str

    @classmethod
    def from_DrawnCard(cls, drawn_card: DrawnCard) -> "CardPreview":
        # in the future might be able to preview more checks so leaving them as lists
        return CardPreview(id=drawn_card.card.id, name=drawn_card.card.name, checks=drawn_card.card.checks[0
:1], choice_type=drawn_card.card.choice_type, choices=drawn_card.card.choices[0:1], age=drawn_card.age, location_name=drawn_card.location_name)


@dataclass(frozen=True)
class Encounter:
    name: str
    desc: str
    checks: Sequence[EncounterCheck]
    choice_type: ChoiceType
    choices: Sequence[Sequence[Effect]]
    signs: Sequence[str]
    rolls: Sequence[int]

    @classmethod
    def from_engine_Encounter(self, encounter: engine_Encounter) -> "Encounter":
        return Encounter(name=encounter.card.name, desc=encounter.card.desc, checks=encounter.card.checks, choice_type=encounter.card.choice_type, choices=encounter.card.choices, signs=encounter.card.signs, rolls=encounter.rolls)


@dataclass(frozen=True)
class Character:
    name: str
    player_id: str
    skills: Dict[str, int]
    skill_xp: Dict[str, int]
    job: str
    health: int
    coins: int
    resources: int
    reputation: int
    quest: int
    location: str
    remaining_turns: int
    luck: int
    tableau: Sequence[CardPreview]
    encounters: Sequence[Encounter]

    @classmethod
    def from_engine_Character(cls, ch: engine_Character) -> "Character":
        return Character(
            name=ch.name,
            player_id=ch.player_id,
            skills=ch.skills,
            skill_xp=ch.skill_xp,
            job=ch.job,
            health=ch.health,
            coins=ch.coins,
            resources=ch.resources,
            reputation=ch.reputation,
            quest=ch.quest,
            location=ch.location,
            remaining_turns=ch.remaining_turns,
            luck=ch.luck,
            tableau=tuple(CardPreview.from_DrawnCard(card) for card in ch.tableau),
            encounters=tuple(Encounter.from_engine_Encounter(enc) for enc in ch.encounters),
        )

@dataclass(frozen=True)
class JobRequest:
    card_id: int


@dataclass(frozen=True)
class JobResponse:
    pass


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


@dataclass(frozen=True)
class ResolveEncounterRequest:
    actions: EncounterActions


@dataclass(frozen=True)
class ResolveEncounterResponse:
    outcome: EncounterOutcome


class ErrorType(Enum):
    UNKNOWN = 0
    ILLEGAL_MOVE = 1
    BAD_STATE = 2


@dataclass(frozen=True)
class ErrorResponse:
    type: ErrorType
    message: str
